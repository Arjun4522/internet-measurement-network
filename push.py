import asyncio
import json
from nats.aio.client import Client as NATS


async def test_modules():
    nc = NATS()
    await nc.connect(servers=["nats://127.0.0.1:4222"])

    # Subscribe to output and error subjects
    async def make_printer(label):
        async def cb(msg):
            data = msg.data.decode()
            print(f"[{label}] {msg.subject}: {data}")
        return cb

    await nc.subscribe("agent.WorkingModule.out", cb=await make_printer("OUTPUT"))
    await nc.subscribe("agent.WorkingModule.error", cb=await make_printer("ERROR"))
    await nc.subscribe("agent.FaultyModule.out", cb=await make_printer("OUTPUT"))
    await nc.subscribe("agent.FaultyModule.error", cb=await make_printer("ERROR"))

    # Publish to WorkingModule
    await nc.publish("agent.WorkingModule.in", json.dumps({
        "msg": "Hello from WorkingModule"
    }).encode())

    # Publish to FaultyModule - normal
    await nc.publish("agent.FaultyModule.in", json.dumps({
        "msg": "Normal message"
    }).encode())

    # Publish to FaultyModule - simulate delay
    await nc.publish("agent.FaultyModule.in", json.dumps({
        "msg": "Please delay", "delay": 1.5
    }).encode())

    # Publish to FaultyModule - simulate crash
    await nc.publish("agent.FaultyModule.in", json.dumps({
        "msg": "Trigger crash", "crash": True
    }).encode())

    # Publish to FaultyModule - duplicate check
    await nc.publish("agent.FaultyModule.in", json.dumps({
        "id": "abc123", "msg": "Original"
    }).encode())
    await nc.publish("agent.FaultyModule.in", json.dumps({
        "id": "abc123", "msg": "Duplicate"
    }).encode())

    print("📤 Messages sent. Waiting for responses...")

    await asyncio.sleep(5)  # Give time to receive all messages
    await nc.drain()


if __name__ == "__main__":
    asyncio.run(test_modules())
