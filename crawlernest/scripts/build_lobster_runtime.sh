#!/bin/bash

TARGET=lobster-runtime

rm -rf $TARGET
mkdir -p $TARGET

cp crawlernest/run_pipeline.py $TARGET/
cp -r crawlernest/pipeline $TARGET/
cp -r crawlernest/crawlernest-core $TARGET/
cp -r crawlernest/crawlernest-db-writer $TARGET/
cp -r crawlernest/crawlernest-extractors $TARGET/
cp -r crawlernest/crawlernest-jobs $TARGET/
cp -r crawlernest/crawlernest-schema $TARGET/
cp -r crawlernest/scripts $TARGET/
cp requirements.txt $TARGET/

echo "Lobster runtime build complete."