#!/bin/bash

LOCALE_DIR="$1"
PO_PATH="$2"

PO_LOCALE=$(basename $PO_PATH | sed 's/.po$//' -)

echo "Compiling translations for locale ${PO_LOCALE}"
mkdir -p "${LOCALE_DIR}/${PO_LOCALE}/LC_MESSAGES"
msgfmt -o "${LOCALE_DIR}/${PO_LOCALE}/LC_MESSAGES/stagescript.mo" "${PO_PATH}"
