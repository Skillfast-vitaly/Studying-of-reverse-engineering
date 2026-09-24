# Сборка учебных задач под Windows, в консоли w64devkit (глава 6).
#
#   make          — собрать задачи в папку build/
#   make hard     — «тяжёлый режим»: -O2 и без имён функций (-s),
#                   как в настоящих программах. Для второго прохода.
#   make test     — проверить, что задачи решаемы. СПОЙЛЕРЫ: в выводе ответы!
#   make clean    — удалить собранное
#
# Флаги подобраны так, чтобы новичку было ЛЕГЧЕ разбирать:
#   -O0   без оптимизаций — ассемблер похож на исходник (глава 2)
#
# Задача 04 (анти-отладка) пока написана под Linux. Под Windows её
# переделаем к главе 19, поэтому здесь её нет.

CC      := gcc
CFLAGS  := -O0 -Wall -Wextra
BUILD   := build
SRC     := src

NAMES   := 01_strings 02_xor 03_serial 05_vm
TARGETS := $(addprefix $(BUILD)/,$(addsuffix .exe,$(NAMES)))

.PHONY: all hard clean test help

all: $(TARGETS)
	@echo ""
	@echo "Gotovo. Programmy lezhat v $(BUILD)/"
	@echo "Nachni s:  ./$(BUILD)/01_strings.exe"

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.exe: $(SRC)/%.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(BUILD)/05_vm.exe: $(SRC)/05_vm_program.h

hard: | $(BUILD)
	@for n in $(NAMES); do \
		$(CC) -O2 -s -o $(BUILD)/$$n.hard.exe $(SRC)/$$n.c || exit 1; \
		echo "  sobrano $(BUILD)/$$n.hard.exe"; \
	done

# Проверка, что задачи вообще решаемы: прогоняем заведомо верные ответы.
# ВНИМАНИЕ: здесь ответы. Не смотри, пока решаешь сам.
test: all
	@echo "== smoke-test (spoilers!) =="
	@printf 'rev_is_fun_2024\n'   | ./$(BUILD)/01_strings.exe | tail -1
	@printf 'xor_hides_nothing\n' | ./$(BUILD)/02_xor.exe     | tail -1
	@printf 'RE-6685000-I\n'      | ./$(BUILD)/03_serial.exe  | tail -1
	@printf 'vm_obfuscation\n'    | ./$(BUILD)/05_vm.exe      | tail -1

clean:
	rm -rf $(BUILD)

help:
	@echo "make       - sobrat zadachi"
	@echo "make hard  - optimizirovannye versii bez imyon"
	@echo "make test  - proverit reshaemost (SPOILERY)"
	@echo "make clean - udalit sobrannoe"
