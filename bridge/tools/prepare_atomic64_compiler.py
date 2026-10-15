#!/usr/bin/env python3
"""Enable only documented GK104 uint64 ADD/EXCH/CAS encodings in isolated NAK."""
from pathlib import Path
import difflib,hashlib,json
root=Path(__file__).resolve().parents[1]
p=root/'vendor/mesa-26.2.4/src/nouveau/compiler/nak/sm20.rs';old=p.read_text()
marker='GK104 supports U64 ADD/EXCH/CAS, not the full Kepler B set.'
if marker in old:print('Atomic64 compiler change already applied');raise SystemExit(0)
new=old
needle='''        if self.dst.is_none() {
            e.set_opcode(SM20Unit::Mem, 0x1);
        } else {
            e.set_opcode(SM20Unit::Mem, 0x11);
        }
'''
replacement='''        // EXCH/CAS always use the returning instruction, with rZ when unused.
        // The reduction encoding has no exchange or compare-exchange form.
        let reduction = self.dst.is_none()
            && !matches!(self.atom_op, AtomOp::Exch | AtomOp::CmpExch(_));
        if reduction {
            e.set_opcode(SM20Unit::Mem, 0x1);
        } else {
            e.set_opcode(SM20Unit::Mem, 0x11);
        }
'''
assert new.count(needle)==1;new=new.replace(needle,replacement,1)
needle='''            AtomType::U64 | AtomType::I64 | AtomType::F64 => {
                // They encode fine:
                //
                //     AtomType::U64 => 0x5_u8,
                //     AtomType::I64 => 0x8_u8,
                //     AtomType::F64 => 0xc_u8,
                //
                // but the hardware throws an ILLEGAL_INSTRUCTION_ENCODING error
                // if we ever actually execute one.  Also, the proprietary
                // driver doesn't expose any 64-bit atomic features on Kepler A.
                panic!("64-bit atomics are not supported");
            }
'''
replacement='''            // GK104 supports U64 ADD/EXCH/CAS, not the full Kepler B set.
            // Matches the existing Nouveau NVC0 emitter and GF100 ISA tables.
            AtomType::U64 => {
                assert!(matches!(self.atom_op,
                    AtomOp::Add | AtomOp::Exch | AtomOp::CmpExch(_)),
                    "Unsupported SM20/SM30 uint64 atomic operation");
                0x5_u8
            }
            // Native double atomics and the signed64/min/max/bitwise family
            // remain unqualified on this backend.
            AtomType::I64 | AtomType::F64 => {
                panic!("Unsupported SM20/SM30 64-bit atomic type");
            }
'''
assert needle in new;new=new.replace(needle,replacement,1)
start=new.index('impl SM20Op for OpAtom {');end=new.index('\nimpl SM20Op for OpAL2P',start)
part=new[start:end];needle='''        if self.dst.is_none() {
            e.set_field(26..58, self.addr_offset);
''';assert needle in part;part=part.replace(needle,'''        if reduction {
            e.set_field(26..58, self.addr_offset);
''',1)
part=part.replace('''        } else if !self.dst.is_none() {
            e.set_reg_src(49..55, &0.into());
''','''        } else if !reduction {
            e.set_reg_src(49..55, &0.into());
''',1)
new=new[:start]+part+new[end:]
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/nouveau/compiler/nak/sm20.rs',tofile='b/src/nouveau/compiler/nak/sm20.rs'))
p.write_text(new);(root/'src/mesa-26.2.4-atomic64-import.patch').write_text(patch)
(root/'results/atomic64-compiler-patch.json').write_text(json.dumps({'file':str(p.relative_to(root)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'scope':'uint64 global add/exchange/compare-exchange only; no full64bit atomic feature declaration','reference':'src/gallium/drivers/nouveau/codegen/nv50_ir_emit_nvc0.cpp::emitATOM'},indent=2)+'\n')
print('Applied restricted uint64 atomic encodings to isolated compiler source')
