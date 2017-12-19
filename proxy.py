from aiohttp import web

async def handle(request):
    print(request.match_info.get('path'), request.headers)
    name = request.match_info.get('name', "Anonymous")
    text = "Hello, " + name
    return web.Response(text=text)

app = web.Application()
app.router.add_get('/{path:.*}', handle_info)

web.run_app(app)