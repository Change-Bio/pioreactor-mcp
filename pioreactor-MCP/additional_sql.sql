-- Remember to add the parser and TopicToParserToTable in PLUGIN.py to send to the db (see https://docs.pioreactor.com/developer-guide/plugin-as-python-package)
CREATE TABLE IF NOT EXISTS READINGS (
    experiment               TEXT NOT NULL,
    pioreactor_unit          TEXT NOT NULL,
    timestamp                TEXT NOT NULL,
    READING_NAME          REAL
);
