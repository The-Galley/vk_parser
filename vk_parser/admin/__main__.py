import logging

from aiomisc import Service, entrypoint
from aiomisc_log import basic_config

from vk_parser.admin.arguments import parser
from vk_parser.admin.deps import config_deps
from vk_parser.admin.service import Admin

log = logging.getLogger(__name__)


def main() -> None:
    args = parser.parse_args()
    basic_config(level=args.log_level, log_format=args.log_format)
    config_deps(args)

    services: list[Service] = [
        Admin(
            address=args.api_address,
            port=args.api_port,
        ),
    ]

    with entrypoint(
        *services,
        log_level=args.log_level,
        log_format=args.log_format,
        pool_size=args.pool_size,
        debug=args.debug,
    ) as loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
