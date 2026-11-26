#!/usr/bin/env python3
"""Start or query the saved E5 workflow through the running Demo API."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment_id', help='已保存的原 E5 实验 ID')
    parser.add_argument('--api', default='http://127.0.0.1:8010', help='Demo 后端地址')
    parser.add_argument('--status', action='store_true', help='仅查询进度')
    args = parser.parse_args(argv)
    path = f"{args.api.rstrip('/')}/api/experiments/{quote(args.experiment_id, safe='')}"
    request = Request(path + ('?light=true' if args.status else '/run-cycle?target=release'),
                      method='GET' if args.status else 'POST')
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
    except HTTPError as error:
        print(error.read().decode(errors='replace'))
        return 1
    except URLError as error:
        print(f'Demo 后端不可用：{error.reason}')
        return 1
    if args.status:
        result = result.get('result', {}).get('optimization_cycle', {})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
