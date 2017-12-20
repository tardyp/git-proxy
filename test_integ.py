from proxy import make_app
import asyncio.subprocess
import proxy
import os
creds = os.environ["CREDS"]

async def test_bad_url(test_client, loop):
    app = make_app()
    client = await test_client(app)
    resp = await client.get('/')
    assert resp.status == 403

async def test_basic(test_client, loop, tmpdir):
    proxy.workdir = str(tmpdir / "workdir")
    app = make_app()

    client = await test_client(app)
    url = "http://{}@localhost:{}/repo_test/manifest".format(creds, client._server.port)
    tmpdir.chdir()
    proc = await asyncio.create_subprocess_exec("git", "clone", url)
    assert (await proc.wait()) == 0
