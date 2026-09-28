-- Run in MySQL Workbench as your local administrator.
CREATE DATABASE IF NOT EXISTS liquor_analytics CHARACTER SET utf8mb4;
-- Replace the placeholder password locally. Never commit your actual password.
CREATE USER IF NOT EXISTS 'liquor_app'@'localhost' IDENTIFIED BY 'REPLACE_THIS_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, REFERENCES, CREATE VIEW, SHOW VIEW, DROP
ON liquor_analytics.* TO 'liquor_app'@'localhost';
-- DROP is needed by CREATE OR REPLACE VIEW. The application never drops source tables.
