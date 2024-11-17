#!/usr/bin/bash
ssh well@10.0.0.141 'cd prog/mouseadmin && git pull origin master && scripts/deploy.sh'
