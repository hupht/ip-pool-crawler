import redis

from crawler.runtime import load_settings


def run() -> None:
    # 使用配置中的 Redis 连接信息进行连通性检测
    settings = load_settings()
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )

    try:
        ok = client.ping()
        print(f"redis_ping {ok}")
    except Exception as exc:
        print(f"redis_error {type(exc).__name__} {exc}")


if __name__ == "__main__":
    run()
