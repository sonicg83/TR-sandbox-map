import pytest
from trmap.imports.sql import parse_map_sql
from trmap.imports.scan import parse_scan_json


def test_sql_escaped_text_and_null():
    sql = "INSERT INTO `x_world` VALUES (14,-187,200,1,51213,'O\\'Brien,村',1029,'玩家',31,'联盟',NULL,NULL,FALSE,NULL,NULL,NULL);"
    record = parse_map_sql(sql)[0]
    assert record['village_name'] == "O'Brien,村"
    assert record['population'] is None
    assert (record['x'], record['y']) == (-187, 200)


def test_sql_rejects_unexpected_commands():
    with pytest.raises(ValueError):
        parse_map_sql('DROP TABLE worlds;')


def test_scan_rejects_cross_category_duplicate():
    with pytest.raises(ValueError):
        parse_scan_json('{"schema_version":1,"metadata":{},"tiles":[{"x":1,"y":2,"kind":"village","static":{"resources":null},"observations":[]},{"x":1,"y":2,"kind":"landscape","static":{"landscape_type":"forest"},"observations":[]}]}')
