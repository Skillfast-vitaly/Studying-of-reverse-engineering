# Сборка учебных crackme.
#
# Флаги подобраны так, чтобы бинарник было ЛЕГЧЕ разбирать новичку:
#   -O0                    без оптимизаций — код в ассемблере похож на исходник
#   -no-pie                фиксированные адреса — в objdump и gdb они совпадают
#   -fno-stack-protector   без защитных «канареек», меньше лишнего шума
#
# В реальной жизни всё наоборот: -O2, PIE, стрипнутые символы. Когда освоишь
# базу — пересобери через `make hard` и почувствуй разницу.

CC      := gcc
CFLAGS  := -O0 -no-pie -fno-stack-protector -Wall -Wextra
BUILD   := build
SRC     := src

NAMES   := 01_strings 02_xor 03_serial 04_antidebug 05_vm
TARGETS := $(addprefix $(BUILD)/,$(NAMES))
STRIPPED := $(addsuffix .stripped,$(TARGETS))

.PHONY: all stripped hard clean test help

all: $(TARGETS)
	@echo ""
	@echo "Готово. Бинарники лежат в $(BUILD)/"
	@echo "Начни с:  ./$(BUILD)/01_strings"

$(BUILD):
	@mkdir -p $(BUILD)

$(BUILD)/%: $(SRC)/%.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# Версии без таблицы символов — имена функций не видны, как в реальном софте.
stripped: $(STRIPPED)

$(BUILD)/%.stripped: $(BUILD)/%
	cp $< $@
	strip $@

# «Тяжёлый режим»: оптимизация, PIE, без символов. Для второго прохода курса.
hard: | $(BUILD)
	@for n in $(NAMES); do \
		$(CC) -O2 -pie -fPIE -s -o $(BUILD)/$$n.hard $(SRC)/$$n.c || exit 1; \
		echo "  собрано $(BUILD)/$$n.hard"; \
	done

# Проверка, что задачи вообще решаемы — прогоняем заведомо верные ответы.
# ВНИМАНИЕ: содержит ответы. Не смотри в вывод, пока решаешь сам.
test: all
	@echo "== smoke-тест (спойлеры!) =="
	@printf 'rev_is_fun_2024\n'      | ./$(BUILD)/01_strings    | tail -1
	@printf 'xor_hides_nothing\n'    | ./$(BUILD)/02_xor        | tail -1
	@printf 'RE-6685000-I\n'         | ./$(BUILD)/03_serial     | tail -1
	@printf 'ptrace_is_not_enough\n' | ./$(BUILD)/04_antidebug  | tail -1
	@printf 'vm_obfuscation\n'       | ./$(BUILD)/05_vm         | tail -1

clean:
	rm -rf $(BUILD)

help:
	@echo "make          — собрать учебные бинарники"
	@echo "make stripped — собрать версии без символов"
	@echo "make hard     — собрать оптимизированные PIE-версии (сложный режим)"
	@echo "make test     — проверить решаемость (СПОЙЛЕРЫ)"
	@echo "make clean    — удалить собранное"
