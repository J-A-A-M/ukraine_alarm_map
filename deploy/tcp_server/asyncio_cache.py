import asyncio
import aiohttp
import json
import os

map_data_url = os.environ.get('MAP_DATA') or 'http://10.2.0.40:8187/statuses_v1.json'
tcp_port = os.environ.get('TCP_PORT') or 12345

clients = []

previous_data = ""

regions = [
  "Закарпатська область",
  "Івано-Франківська область",
  "Тернопільська область",
  "Львівська область",
  "Волинська область",
  "Рівненська область",
  "Житомирська область",
  "Київська область",
  "Чернігівська область",
  "Сумська область",
  "Харківська область",
  "Луганська область",
  "Донецька область",
  "Запорізька область",
  "Херсонська область",
  "АР Крим",
  "Одеська область",
  "Миколаївська область",
  "Дніпропетровська область",
  "Полтавська область",
  "Черкаська область",
  "Кіровоградська область",
  "Вінницька область",
  "Хмельницька область",
  "Чернівецька область",
  "м. Київ",
]


async def handle_client(reader, writer):
    global previous_data
    writer.write(previous_data.encode())
    await writer.drain()

    clients.append(writer)
    print(f"New client connected from {writer.get_extra_info('peername')}")

    while True:
        try:
            data = await reader.read(1024)
            if not data:
                break
        except:
            break

    clients.remove(writer)  # Remove client writer from the list
    print(f"Client from {writer.get_extra_info('peername')} disconnected")
    writer.close()


async def main(host, port):
    server = await asyncio.start_server(
        handle_client, host, port
    )

    async with server:
        await server.serve_forever()


async def parse_and_broadcast(server, clients):
    global previous_data
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(map_data_url)  # Replace with your URL
                new_data = await response.text()
                parsed_data = json.loads(new_data)

            tcp_data = []
            for region in regions:
                tcp_data.append(1 if parsed_data['states'][region]['enabled'] else 0)

            tcp_data = ":".join(map(str, tcp_data))

            if tcp_data != previous_data:
                print("Data changed. Broadcasting to clients...")
                for client_writer in clients:
                    client_writer.write(tcp_data.encode())
                    await client_writer.drain()

                previous_data = tcp_data
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(5)


async def log_clients_periodically(clients):
    while True:
        print(f"Number of connected clients: {len(clients)}")
        await asyncio.sleep(10)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    server = loop.run_until_complete(asyncio.start_server(
        handle_client, "0.0.0.0", tcp_port
    ))

    asyncio.ensure_future(parse_and_broadcast(server, clients))
    asyncio.ensure_future(log_clients_periodically(clients))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
