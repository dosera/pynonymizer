from datetime import date, datetime
from pynonymizer.database.exceptions import UnsupportedColumnStrategyError
from pynonymizer.strategy.update_column import UpdateColumnStrategyTypes
"""
All Static query generation functions
"""


def _get_column_subquery(seed_table_name, column_name, column_strategy):
    # For preservation of unique values across versions of mysql, and this bug:
    # https://bugs.mysql.com/bug.php?id=89474, use md5 based rand subqueries

    if column_strategy.strategy_type == UpdateColumnStrategyTypes.EMPTY:
        return "('')"
    elif column_strategy.strategy_type == UpdateColumnStrategyTypes.UNIQUE_EMAIL:
        return "( SELECT CONCAT(MD5(FLOOR((NOW() + RAND()) * (RAND() * RAND() / RAND()) + RAND())), '@', MD5(FLOOR((NOW() + RAND()) * (RAND() * RAND() / RAND()) + RAND())), '.com') )"
    elif column_strategy.strategy_type == UpdateColumnStrategyTypes.UNIQUE_LOGIN:
        return "( SELECT CONCAT(MD5(FLOOR((NOW() + RAND()) * (RAND() * RAND() / RAND()) + RAND())))) )"
    elif column_strategy.strategy_type == UpdateColumnStrategyTypes.FAKE_UPDATE:
        return f"( SELECT `{column_strategy.fake_column.column_name}` FROM `{seed_table_name}` ORDER BY RAND() LIMIT 1)"
    elif column_strategy.strategy_type == UpdateColumnStrategyTypes.LITERAL:
        return column_strategy.value
    else:
        raise UnsupportedColumnStrategyError(column_strategy)


def _escape_sql_value(column):
    """
    return a sql-ified version of a seed column's value
    Normally this defines the stringification of datatypes and escaping for strings
    """
    value = column.get_value()
    if isinstance(value, (str, datetime, date)):
        return "'" + str(value).replace("'", "''") + "'"
    else:
        return str(value)


def get_truncate_table(table_name):
    return f"SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE `{table_name}`; SET FOREIGN_KEY_CHECKS=1;"


def get_create_seed_table(table_name, columns):
    if len(columns) < 1:
        raise ValueError("Cannot create a seed table with no columns")

    column_types = ",".join(map(lambda col: f"`{col.column_name}` {col.sql_type}", columns))
    return f"CREATE TABLE `{table_name}` ({column_types});"


def get_drop_seed_table(table_name):
    return f"DROP TABLE IF EXISTS `{table_name}`;"


def get_insert_seed_row(table_name, columns):
    column_names = ",".join(map(lambda col: f"`{col.column_name}`", columns))
    column_values = ",".join(map(lambda col: _escape_sql_value(col), columns))

    return f"INSERT INTO `{table_name}`({column_names}) VALUES ({column_values});"


def get_create_database(database_name):
    return f"CREATE DATABASE `{database_name}`;"


def get_drop_database(database_name):
    return f"DROP DATABASE IF EXISTS `{database_name}`;"


def get_update_table(seed_table_name, table_name, column_strategies):
    # group on where_condition
    grouped_columns = {}
    for column_name, column_strategy in column_strategies.items():
        where_condition = column_strategy.where_condition
        if where_condition not in grouped_columns:
            grouped_columns[where_condition] = {}

        grouped_columns[where_condition][column_name] = column_strategy

    # build lists of update statements based on the where
    output_statements = []
    where_update_statements = {}
    for where, column_map in grouped_columns.items():
        for column_name, column_strategy in column_map.items():
            if where not in where_update_statements:
                where_update_statements[where] = []

            where_update_statements[where].append(f"`{column_name}` = {_get_column_subquery(seed_table_name, column_name, column_strategy)}")

        assignments = ",".join( where_update_statements[where] )
        where_clause = f" WHERE {where}" if where else ""

        output_statements.append( f"UPDATE `{table_name}` SET {assignments}{where_clause};")

    return output_statements


def get_dumpsize_estimate(database_name):
    return f"SELECT data_bytes FROM (SELECT SUM(data_length) AS data_bytes FROM information_schema.tables WHERE table_schema = '{database_name}') AS data;"