import asyncio
import json
import os
import random
from pathlib import Path

from aiohttp import web, WSMsgType

rooms = {}  # room_id -> {'players': [ws, ...], 'seed': int}


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    room_id = None
    try:
        raw = await ws.receive_str()
        data = json.loads(raw)
        room_id = str(data.get('room', '0000')).zfill(4)

        if room_id not in rooms:
            rooms[room_id] = {'players': [], 'seed': random.randint(1, 999999)}

        room = rooms[room_id]

        if len(room['players']) >= 2:
            await ws.send_str(json.dumps({'type': 'error', 'msg': '部屋が満員です'}))
            return ws

        room['players'].append(ws)
        role = f"player{len(room['players'])}"

        await ws.send_str(json.dumps({
            'type': 'joined',
            'role': role,
            'seed': room['seed']
        }))
        print(f"[{room_id}] {role} joined")

        if len(room['players']) == 2:
            for player_ws in room['players']:
                await player_ws.send_str(json.dumps({
                    'type': 'game_start',
                    'seed': room['seed']
                }))
            print(f"[{room_id}] game started (seed={room['seed']})")

        # メッセージをもう一方のプレイヤーへ中継
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                for player_ws in room['players']:
                    if player_ws is not ws:
                        await player_ws.send_str(msg.data)
            elif msg.type == WSMsgType.ERROR:
                break

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if room_id and room_id in rooms:
            room = rooms[room_id]
            if ws in room['players']:
                room['players'].remove(ws)
                print(f"[{room_id}] player disconnected ({len(room['players'])} remaining)")
            for player_ws in room['players']:
                try:
                    await player_ws.send_str(json.dumps({'type': 'opponent_left'}))
                except Exception:
                    pass
            if not room['players']:
                del rooms[room_id]

    return ws


async def index_handler(request):
    return web.FileResponse(Path(__file__).parent / 'card_game.html')


def create_app():
    app = web.Application()
    app.router.add_get('/ws', websocket_handler)
    app.router.add_get('/', index_handler)
    # 画像フォルダを静的ファイルとして配信
    images_dir = Path(__file__).parent / 'images'
    if images_dir.exists():
        app.router.add_static('/images', images_dir)
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8081))
    print(f"Starting server on port {port}...")
    web.run_app(create_app(), host='0.0.0.0', port=port)
