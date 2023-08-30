#!/usr/bin/bash
ssh wellpi@10.0.0.102 'cd prog/mouseadmin && git pull origin master && scripts/deploy.sh'
