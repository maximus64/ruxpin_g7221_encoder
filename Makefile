CFLAGS := -Wall -Wextra -Wno-unused-parameter -Werror \
	-D__unix__

OBJECTS := \
	encode.o \
	encoder.o \
	common.o \
	huff_tab.o \
	tables.o \
	sam2coef.o \
	dct4_a.o \
	count.o \
	basop32.o

BUILD_OBJS := $(patsubst %,build/%,$(OBJECTS))

.PHONY: all clean

all: build/encode

clean:
	rm -rf build/*

$(BUILD_OBJS): build/%.o: %.c
	@echo "  CC    $@"
	@mkdir -p "$(dir $@)"
	@$(CC) -c $(CFLAGS) -o $@ $<

build/encode: $(BUILD_OBJS)
	@echo "  CC    $@"
	@$(CC) $(CFLAGS) -o $@ $(BUILD_OBJS)
