# positronic_serve/cli.py
import argparse
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="positronic-serve",
                                description="PEEP network layer (port 2114)")
    p.add_argument("--config-dir", default=".", help="dir holding .positronic + serve.json")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args(argv)

    from positronic_serve.config import load_config
    from positronic_serve.server import create_app

    cfg = load_config(args.config_dir)
    host = args.host or cfg.get("host", "127.0.0.1")
    port = args.port or cfg.get("port", 2114)

    import uvicorn
    uvicorn.run(create_app(cfg), host=host, port=port,
                reload=args.reload, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())