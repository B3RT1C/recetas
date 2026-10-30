"""Start the Recetas web server.  Usage: python run.py [--host 0.0.0.0] [--port 8088] [--mock-instagram]"""
import argparse
import os


def main() -> None:
    ap = argparse.ArgumentParser(description="Recetario C — servidor web")
    ap.add_argument("--host", default=os.environ.get("RECETAS_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("RECETAS_PORT", "8088")))
    ap.add_argument("--videos-dir", help="carpeta con los vídeos <SHORTCODE>.mp4 (RECETAS_VIDEOS_DIR)")
    ap.add_argument("--mock-instagram", action="store_true", help="usa el proveedor de Instagram simulado (demo/tests)")
    args = ap.parse_args()
    os.environ["RECETAS_HOST"], os.environ["RECETAS_PORT"] = args.host, str(args.port)
    if args.videos_dir:
        os.environ["RECETAS_VIDEOS_DIR"] = args.videos_dir
    if args.mock_instagram:
        os.environ["RECETAS_IG_PROVIDER"] = "mock"
    import uvicorn
    from app.main import create_app
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
