from aiohttp import web, ClientSession
import asyncio.subprocess
import io
import os
import logging
import base64

log = logging.getLogger(__name__)

upstream = os.environ.get("GITSERVER_UPSTREAM", None)
workdir = os.environ.get("WORKING_DIRECTORY", None)

def find_gitpath(path):
    """find the git path for this url path
    ensures it ends with ".git", and do not start with "/"
    """
    assert path.startswith("/"), path
    for suffix in (".git/info/refs", ".git/git-upload-pack", "/info/refs", "/git-upload-pack"):
        if path.endswith(suffix):
            return path[1:-len(suffix)] + ".git"
    raise ValueError("bad path: " + path)

def get_session(request):
    """automatically create a shared session for http proxying
    @todo: http_proxy is not automatically handled apparently
    """
    if not hasattr(request.app, "proxysession"):
        request.app.proxysession = ClientSession()

    return request.app.proxysession

def find_directory(path):
    """find the working directory of the repository path"""
    assert workdir
    d = os.path.join(workdir, path)
    if not os.path.isdir(d):
        os.makedirs(d)
    return d

class UploadPackHandler(object):
    """Unit testable upload-pack handler which automatically call git fetch to update the local copy
    @todo: locking!
    
    """
    def __init__(self, path, auth):
        self.directory = find_directory(path)
        self.upstream_url = upstream + path
        for proto in "http", "https":
            self.upstream_url = self.upstream_url.replace(proto + "://", proto + "://" + auth + "@")

    async def run(self, input):
        """Start the process upload-pack process optimistically.
        Fetch the first line of result to see if there is an error.
        If there is no error, the process output is forwarded to the http client.
        If there is an error, git fetch or git clone are done.

        @todo: DOS attack: a authenticated client can trigger a cache removal and git clone by sending a random "want" commit 
        """
        num_try = 0
        self.error = None
        while num_try < 3:
            self.proc = await asyncio.create_subprocess_exec("git", 'upload-pack', '--stateless-rpc', self.directory.encode(),
                                                            stdout=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            self.proc.stdin.write(input)
            firstline =  await self.proc.stdout.readline()
            if not(firstline) or self.proc.returncode != None or firstline[4:7] == b"ERR":
                error = await self.proc.stderr.readline()
                await self.proc.wait()
                num_try += 1
                if num_try == 1:
                    fetch_proc = await asyncio.create_subprocess_exec("git", 'fetch', self.upstream_url, self.directory.encode())
                    await fetch_proc.wait()
                elif num_try == 2:
                    clone_proc = await asyncio.create_subprocess_exec("rm", '-rf', self.upstream_url, self.directory.encode())
                    await clone_proc.wait()
                    clone_proc = await asyncio.create_subprocess_exec("git", 'clone', '--bare', self.upstream_url, self.directory.encode())
                    await clone_proc.wait()
                else:
                    self.error = error
                    self.firstline = firstline
            else:
                self.firstline = firstline
                break

    async def read(self):
        """Read the remaining output of uploadpack, and forward it to the http client
        @todo. See if we can connect the sockets via sendfile or similar, which allows to send the output of git upload-pack directly without going through python (for best performance)
        """
        self.firstline, firstline = None, self.firstline
        if firstline:
            return firstline
        ret = await self.proc.stdout.read()
        if not ret:
            await self.proc.wait()
        return ret


async def handle(server_request):
    """First part of the git+http protocol. Send the list of the refs
    At the moment, this request is not caching. The request is always proxied to the upstream server
    """
    path = server_request.path
    service = server_request.query.get('service')
    if not path.endswith("info/refs") or service != 'git-upload-pack':
        return web.Response(text='mirroring only supports fetch operations', status=403)

    path = find_gitpath(path)
    assert upstream

    if ("Authorization" not in server_request.headers):
        # quickly for git to send basicauth (without upstream round-trip)
        return web.Response(status=401, headers={'WWW-Authenticate': 'Basic realm="Git Proxy"'})

    # proxy the request to the upstream server (forwarding the BasicAuth as well)
    upstream_url = upstream + path + "/info/refs?service=git-upload-pack"
    async with get_session(server_request).get(upstream_url, headers=server_request.headers) as request:
        if request.status != 200:
            log.info("upstream returned error: {} {}: {} {} {}".format(upstream_url,
                    request.status, request.reason, request.headers, await request.content.read()))
            return web.Response(text=request.reason, status=request.status)
        response = web.StreamResponse(status=200,
                                        headers=request.headers)
        await response.prepare(server_request)
        # @todo: use sendfile for proxying
        while True:
            chunk = await request.content.readany()
            if not chunk:
                break
            response.write(chunk)
        return response

async def handle_post(server_request):
    """Second part of the git+http protocol.
    This part creates the git-pack bundle fully locally if possible.
    The authentication is still re-checked (because we are stateless, we can't assume that the client has the rights to access)

    @todo see how we can do fully local by caching the authentication results in a local db (redis?)
    """
    path = server_request.path
    if not path.endswith('git-upload-pack'):
        return web.Response(text='mirroring only supports fetch operations', status=403)
    path = find_gitpath(path)

    # proxy a HEAD request to the upstream server (forwarding the BasicAuth as well) to check repo existence and credentials
    upstream_url = upstream + path + "/HEAD"
    auth = server_request.headers['Authorization']
    headers = {'Authorization': auth}
    async with get_session(server_request).get(upstream_url, headers=headers) as request:
        await request.content.read()
        if request.status != 200:
            return web.Response(text=request.reason, status=request.status)

    # read the upload-pack input from http request
    content = await server_request.content.read()

    directory = find_directory(path)
    # decode the creds from the auth in
    creds = base64.b64decode(auth.split(" ")[-1]).decode()

    # run git-upload-pack
    proc = UploadPackHandler(path, auth=creds)
    await proc.run(content)

    # stream the response to the client
    response = web.StreamResponse(status=200,
                                    headers={
                                            'Content-Type': 'application/x-git-upload-pack-result',
                                            'Cache-Control': 'no-cache'
                                            })
    await response.prepare(server_request)
    while True:
        chunk = await proc.read()
        if not chunk:
            break
        response.write(chunk)

    return response

def make_app():
    app = web.Application()
    app.router.add_get('/{path:.*}', handle)
    app.router.add_post('/{path:.*}', handle_post)
    def on_shutdown(app):
        if hasattr(app, "proxysession"):
            return app.proxysession.close()
    app.on_shutdown.append(on_shutdown)
    return app

app = make_app()

if __name__ == '__main__':
    assert upstream
    assert workdir
    web.run_app(app)
