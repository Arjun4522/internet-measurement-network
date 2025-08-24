import asyncio
from nats.aio.client import Client as NATS


async def debug_all_messages(nats_url="nats://127.0.0.1:4222"):
    nc = NATS()

    await nc.connect(servers=[nats_url])
    print(f"✅ Connected to NATS at {nats_url}")
    print("🔍 Subscribing to all subjects (`>`)...\n")

    async def message_handler(msg):
        subject = msg.subject
        data = msg.data.decode()
        print(f"📨 [{subject}]: {data}")

    # Subscribe to all subjects
    await nc.subscribe(">", cb=message_handler)

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("🛑 Shutting down...")
        await nc.drain()

if __name__ == "__main__":
    asyncio.run(debug_all_messages())
