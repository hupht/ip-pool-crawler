from cli import build_parser


def test_run_quick_args_parse():
    parser = build_parser()

    args = parser.parse_args(["run", "--quick-test", "--quick-record-limit", "2"])

    assert args.command == "run"
    assert args.quick_test is True
    assert args.quick_record_limit == 2
