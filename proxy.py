from aiohttp import web, ClientSession

async def handle(server_request):
    path = server_request.match_info['path']
    print(path)
    if path.endswith("info/refs"):
        async with ClientSession() as session:
            async with session.get("https://github.com/tardyp/git-proxy.git/info/refs?service=git-upload-pack") as request:
                print(request.content_type)
                response = web.StreamResponse(status=200,
                                              headers=request.headers)
                await response.prepare(server_request)
                while True:
                    chunk = await request.content.readany()
                    if not chunk:
                        break
                    response.write(chunk)
                return response

async def handle_post(server_request):
    path = server_request.match_info['path']
    print("post", path)
    content = await server_request.content.read()
    print("post", path, content)
    return web.Response(text='nope')
app = web.Application()
app.router.add_get('/{path:.*}', handle)
app.router.add_post('/{path:.*}', handle_post)

web.run_app(app)