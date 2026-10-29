# Faults that software cannot cause

The Linux kernel logs a record whenever a program is killed by a processor exception. The records below come from
everyday use of this PC (before any diagnostic testing), in standard Ubuntu and PyTorch binaries. For each record we
looked up the instruction at the reported address in the same, unchanged binary.

A working processor raises "invalid opcode" (#UD) only for byte sequences that are not valid instructions. Three
records show #UD on valid instructions, and two more show control flow that no valid execution can produce. Software
bugs, the kernel and the GPU cannot make a valid instruction raise #UD. Corrupted program code in RAM would crash every
later run of the same code, and the memory test passed.

| Date and time | Program | Exception | Instruction at the reported address | Why it is impossible |
|---|---|---|---|---|
| 2026-10-27 20:15:59 | PyTorch `libc10_cuda.so` | invalid opcode | `mov rdx,[rbx+0xf0]` (48 8b 93 f0 00 00 00) | ordinary valid instruction, at an instruction boundary |
| 2026-10-27 20:14:32 | Python 3.12 interpreter | invalid opcode | `push r13` (41 55), start of `PyEval_EvalCode` | ordinary valid instruction, at an instruction boundary |
| 2026-10-13 02:17:47 | PyTorch `libtorch_python.so` | invalid opcode | byte 0x50 = `push rax` | valid one-byte instruction. The address is also the last byte of a `movzx`, so no valid jump leads there |
| 2026-10-10 17:52:16 | Python 3.12 interpreter | invalid opcode | inside a 7-byte `mov` in `_PyEval_EvalFrameDefault` | execution jumped into the middle of an instruction |
| 2026-10-10 17:55:15 | Python 3.12 interpreter | general protection | `endbr64` at the start of `PyException_GetTraceback` | `endbr64` does not access memory and cannot raise a protection fault |

A hardware machine-check event was also logged on 2026-10-13 at 02:20:46, three minutes after the 02:17:47 record.

These trap records do not name the CPU. The kernel names the CPU only for segmentation faults, and there 25 of 30 are
on CPU 0 (see `crash_count_by_cpu.txt`). The table therefore shows that the processor executes instructions incorrectly.
The pinned tests show which core does it.

## Kernel log lines (unedited)

```
2026-10-10T17:52:16+02:00 kernel: traps: python[2391008] trap invalid opcode ip:5dd617 sp:7ffe4b58af70 error:0 in python3.12[1dd617,420000+2e3000]
2026-10-10T17:55:15+02:00 kernel: traps: python[2391573] general protection fault ip:552d00 sp:7ffdf05337b8 error:0 in python3.12[152d00,420000+2e3000]
2026-10-13T02:17:47+02:00 kernel: traps: python[2718717] trap invalid opcode ip:74c1bd0a86bc sp:7ffc9cf48a30 error:0 in libtorch_python.so[8a86bc,74c1bca11000+b0d000]
2026-10-13T02:20:46+02:00 kernel: mce: [Hardware Error]: Machine check events logged
2026-10-27T20:14:32+01:00 kernel: traps: python[1270761] trap invalid opcode ip:5d5ae1 sp:7ffd34092c10 error:0 in python[1d5ae1,420000+2e3000]
2026-10-27T20:15:59+01:00 kernel: traps: python[1272581] trap invalid opcode ip:7fd965b911b8 sp:7fffe20a5060 error:0 in libc10_cuda.so[1e1b8,7fd965b84000+54000]
```

In `name[A,B+C]` the kernel gives the file offset `A` of the faulting instruction, then the start address `B` and size `C`
of the executable mapping. For each library, the size of the executable segment of the file on disk equals `C`, and the
files have not changed since before these dates. The 2026-10-27 20:14:32 record names the program `python`. Its mapping
(`420000+2e3000`) is identical to `/usr/bin/python3.12`, i.e. a copy of the same interpreter.

## Binaries

| File | Package | SHA-256 |
|---|---|---|
| `/usr/bin/python3.12` | Ubuntu 24.04 `python3.12` 3.12.3-1ubuntu0.17 | `e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f` |
| `torch/lib/libc10_cuda.so` | PyPI `torch==2.2.2+cu121` | `390583d25527a37120fecf01c5933a992e35f89a1ec11d8ff061711524f71a67` |
| `torch/lib/libtorch_python.so` | PyPI `torch==2.2.2+cu121` | `6283d61ce548090db7537811a5fd9996a37568064c2b26999025d3a109b4f92f` |

## Disassembly at each address (`=>` marks the reported instruction)

`libc10_cuda.so`, file offset 0x1e1b8 (`DeviceCachingAllocator::free_block`):
```
   1e1af: e9 06 ff ff ff          jmp    1e0ba
   1e1b4: 0f 1f 40 00             nop    DWORD PTR [rax+0x0]
=> 1e1b8: 48 8b 93 f0 00 00 00    mov    rdx,QWORD PTR [rbx+0xf0]
```

`python3.12`, address 0x5d5ae1 (`PyEval_EvalCode`):
```
   5d5adb: 49 89 d6               mov    r14,rdx
   5d5ade: 4c 89 ca               mov    rdx,r9
=> 5d5ae1: 41 55                  push   r13
   5d5ae3: 41 54                  push   r12
```

`libtorch_python.so`, file offset 0x8a86bc (copy constructor of `std::vector<c10::Argument>`); raw bytes
`41 0f b6 44 24 [50] 48 83 c3 58`:
```
   8a86b7: 41 0f b6 44 24 50      movzx  eax,BYTE PTR [r12+0x50]     (0x8a86bc is its last byte, 0x50)
   8a86bd: 48 83 c3 58            add    rbx,0x58
```

`python3.12`, address 0x5dd617 (`_PyEval_EvalFrameDefault`), inside this instruction:
```
   5dd612: 4c 8b ad f8 fe ff ff   mov    r13,QWORD PTR [rbp-0x108]   (0x5dd617 is its 6th byte)
```

`python3.12`, address 0x552d00 (`PyException_GetTraceback`):
```
=> 552d00: f3 0f 1e fa            endbr64
   552d04: 48 8b 47 28            mov    rax,QWORD PTR [rdi+0x28]
```

## Check it yourself

On any x86-64 Linux machine with the same package versions:

```bash
objdump -d -M intel --start-address=0x5d5ad0 --stop-address=0x5d5ae8 /usr/bin/python3.12
objdump -d -M intel --start-address=0x552cf0 --stop-address=0x552d08 /usr/bin/python3.12
pip download torch==2.2.2 --index-url https://download.pytorch.org/whl/cu121 --no-deps -d wheel && unzip -q wheel/*.whl 'torch/lib/libc10_cuda.so' 'torch/lib/libtorch_python.so'
objdump -d -M intel --start-address=0x1e1a0 --stop-address=0x1e1c0 torch/lib/libc10_cuda.so
objdump -d -M intel --start-address=0x8a86a0 --stop-address=0x8a86c5 torch/lib/libtorch_python.so
```

For these shared libraries the executable segment's file offset equals its address, so the file offsets above can be
used directly.

`trap_disasm.sh <binary> <hex file offset> <label>` in this folder prints the same disassembly for any kernel trap
record (`./trap_disasm.sh /usr/bin/python3.12 1d5ae1 example`).
