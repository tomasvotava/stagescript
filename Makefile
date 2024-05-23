LOCALE_DIR=i18n
SRC_DIR=stagescript

.PHONY: pot
pot:
	find $(SRC_DIR) -name '*.py' -exec xgettext -o $(LOCALE_DIR)/stagescript.pot --from-code=UTF-8 -k_ -L Python {} +

.PHONY: translations
translations:
	find $(LOCALE_DIR) -name '*.po' -exec $(LOCALE_DIR)/compile-translations.sh "$(LOCALE_DIR)" "{}" \;
