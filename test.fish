#!/home/well/.nix-profile/bin/fish

if test -e testdb.db
    rm testdb.db
end
sqlite3 testdb.db < schema.sql &&
./puppeteer-test.js &&
rm testdb.db
