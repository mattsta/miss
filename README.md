Matt's Incredible Struct System
===============================

Simple command line script utility to detect inefficient struct padding using dwarf debug output.

I wrote this in 2019 to discover struct padding issues in programs with a
couple hundred structs in the final binary.

The architecture of the program looks very hacky and could be refactored into a "proper" looking
program if anybody wants to take that on.

Originally I had been using [`struct_layout`](https://github.com/arvidn/struct_layout), but
the dwarf text output format changed over time and it was too difficult to update their
logic, so I rewrote just what we needed for struct padding detection.


## Usage

First, compile your source using debug info (`-g`) which will generate a
directory named `[executable].dSYM/`.

Let's use this simple program as `hello.c` in this example:
```c
typedef struct abc {
    int a;
    char b;
    char c;
    double x;
} abc;

int main(void) {
    abc def;
    def.c = 3;
    return 0;
}
```

```bash
$ clang -O0 -g -o hello hello.c
```

Then look inside the directory...

```bash
$ ls -R hello.dSYM/
Contents

hello.dSYM//Contents:
Info.plist Resources

hello.dSYM//Contents/Resources:
DWARF

hello.dSYM//Contents/Resources/DWARF:
hello
```

We want the file in the `DWARF` directory to run through `dwarfdump`:

```bash
$ dwarfdump hello.dSYM/Contents/Resources/DWARF/hello > hello.dump
```

Now `hello.dump` holds a debug text representation of your program, which we
can *now* parse with `parseDwarfDump.py` as:

```bash
$ ./parseDwarfDump.py hello.dump
Compile units: 1
Python memory usage for representation is this big: 12,715 bytes (0.01 MB)
This big (as reference): 13,463 bytes (0.01 MB)
abc
       0 hello.c:2 a (4) (int)
       4 hello.c:3 b (1) (char)
       5 hello.c:4 c (1) (char)
       8 hello.c:5 x (8) (double)
Length: 14 (0.21875 cache lines)
But deployed with padding: 16 (0.25 cache lines)
Optimal would require removing: 2 bytes
```

Assumptions here are a 64-byte cache line (which isn't necessarily true across all platforms).

Utility doesn't attempt to suggest any re-ordering workflows since it should be fairly obvious
where excess padding is appearing (re-ordering all elements from largest to smallest works too).

Also the "optimal" recommendation doesn't account for a struct total size being less than one cache line
where padding wouldn't matter anyway.
