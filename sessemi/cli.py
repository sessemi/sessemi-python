# open sessemi
"""
sessemi CLI — scrape any website from your terminal.

Usage:
    sessemi scrape URL [options]
    sessemi credits
    sessemi health

Examples:
    sessemi scrape "https://www.leboncoin.fr/recherche?category=10" -c FR
    sessemi scrape "https://www.idealista.com/en/venta-viviendas/" -c ES -o listings.html
    sessemi scrape "https://www.nike.com/w/shoes" -f json -o shoes.json
    sessemi credits
"""

import argparse
import json
import os
import sys
import time

from . import Sessemi, SessemiError, __version__


def _get_client():
    key = os.environ.get("SESSEMI_KEY", "")
    if not key:
        print("Error: SESSEMI_KEY not set.\n", file=sys.stderr)
        print("  export SESSEMI_KEY=your_key_here\n", file=sys.stderr)
        print("  Get your free key at https://app.sessemi.com", file=sys.stderr)
        sys.exit(1)
    return Sessemi(key=key)


def cmd_scrape(args):
    client = _get_client()
    start = time.time()

    kwargs = {"url": args.url}
    if args.country:
        kwargs["country"] = args.country
        if not args.pool:
            kwargs["pool"] = "residential"
    if args.pool:
        kwargs["pool"] = args.pool
    if args.session:
        kwargs["session"] = args.session
    if args.method and args.method.upper() != "GET":
        kwargs["method"] = args.method.upper()
    if args.headers:
        try:
            kwargs["headers"] = json.loads(args.headers)
        except json.JSONDecodeError:
            print("Error: --headers must be valid JSON", file=sys.stderr)
            sys.exit(1)
    if args.render:
        kwargs["render"] = True
    if args.screenshot:
        kwargs["screenshot"] = True

    if not args.quiet:
        print(f"Scraping {args.url}...", file=sys.stderr)

    try:
        result = client.scrape(**kwargs)
    except SessemiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start

    if not args.quiet:
        provider = result.challenge_provider or "none"
        solved = " (solved)" if result.solved else ""
        print(
            f"  {result.status_code} | {result.body_size:,} bytes | "
            f"{result.credits_charged} credits | {provider}{solved} | {elapsed:.1f}s",
            file=sys.stderr,
        )

    if args.screenshot and result.screenshot and args.output:
        with open(args.output, "wb") as f:
            f.write(result.screenshot)
        if not args.quiet:
            print(f"  Screenshot saved to {args.output}", file=sys.stderr)
        return

    if args.format == "json":
        output = json.dumps(
            {
                "url": result.url,
                "status_code": result.status_code,
                "body_size": result.body_size,
                "content": result.text,
                "challenge_provider": result.challenge_provider,
                "solved": result.solved,
                "credits_charged": result.credits_charged,
                "duration_ms": result.duration_ms,
                "resolved_url": result.resolved_url,
                "error": result.error,
            },
            indent=2,
            ensure_ascii=False,
        )
    else:
        output = result.text

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        if not args.quiet:
            print(f"  Saved to {args.output}", file=sys.stderr)
    else:
        print(output)


def cmd_credits(args):
    key = os.environ.get("SESSEMI_KEY", "")
    if not key:
        print("Error: SESSEMI_KEY not set.", file=sys.stderr)
        sys.exit(1)

    import urllib.request
    import urllib.error

    base = os.environ.get("SESSEMI_URL", "https://api.sessemi.com")
    req = urllib.request.Request(f"{base}/me", headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        print(f"Error: HTTP {e.code} — {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    tier = data.get("tier", "unknown")
    used = data.get("credits_used", 0)
    limit = data.get("monthly_credits", 0)
    remaining = max(0, limit - used)

    print(f"Tier:      {tier}")
    print(f"Credits:   {used:,} / {limit:,} used")
    print(f"Remaining: {remaining:,}")


def cmd_health(args):
    try:
        client = _get_client()
        h = client.health()
        print(json.dumps(h, indent=2))
    except SessemiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="sessemi",
        description="Sessemi — scrape any website, bypass anti-bot protection.",
        epilog="Docs: https://sessemi.com/docs  |  Free key: https://app.sessemi.com",
    )
    parser.add_argument("--version", action="version", version=f"sessemi {__version__}")
    sub = parser.add_subparsers(dest="command")

    # sessemi scrape
    sp = sub.add_parser("scrape", help="Scrape a URL")
    sp.add_argument("url", help="URL to scrape")
    sp.add_argument("-c", "--country", help="Country code (FR, US, DE, ES, ...)")
    sp.add_argument("-p", "--pool", choices=["residential", "datacenter"],
                    help="Proxy pool (auto-set to residential when country is specified)")
    sp.add_argument("-s", "--session", help="Named session for cookie persistence")
    sp.add_argument("-m", "--method", default="GET", help="HTTP method (default: GET)")
    sp.add_argument("--headers", help='Custom headers as JSON: \'{"Accept": "application/json"}\'')
    sp.add_argument("-f", "--format", choices=["html", "json"], default="html",
                    help="Output format: html (page content) or json (full response)")
    sp.add_argument("-o", "--output", help="Save output to file")
    sp.add_argument("-q", "--quiet", action="store_true", help="Suppress status messages")
    sp.add_argument("--render", action="store_true", help="Force browser rendering")
    sp.add_argument("--screenshot", action="store_true", help="Capture screenshot (use with -o)")

    # sessemi credits
    sub.add_parser("credits", help="Check remaining credits")

    # sessemi health
    sub.add_parser("health", help="Check API health")

    args = parser.parse_args()
    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "credits":
        cmd_credits(args)
    elif args.command == "health":
        cmd_health(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
