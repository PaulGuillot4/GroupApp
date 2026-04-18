import asyncio
import time


async def main():
    print("Notifications service started (placeholder consumer)", flush=True)
    while True:
        print(f"notifications heartbeat ts={int(time.time())}", flush=True)
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
