#!/usr/bin/env python3
"""Apply isolated NAK embedding/texture changes; no system component is edited."""
from pathlib import Path
import difflib
import json
import hashlib

root=Path(__file__).resolve().parents[1]
source=root/'vendor/mesa-26.2.4'
patches=[];records=[]
def edit(relative,marker,transform):
    path=source/relative;old=path.read_text()
    if marker in old:return
    new=transform(old)
    assert new!=old
    patches.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative))
    path.write_text(new)
    records.append({'path':relative,'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()})

def api(old):
    old=old.replace('    has_task_shader: bool,\n) -> *mut nak_shader_bin {\n    unsafe {\n        nak_postprocess_nir',
                    '    has_task_shader: bool,\n    embedded_postprocess: Option<unsafe extern "C" fn(*mut nir_shader, *mut core::ffi::c_void)>,\n    embedded_data: *mut core::ffi::c_void,\n) -> *mut nak_shader_bin {\n    unsafe {\n        nak_postprocess_nir',1)
    needle='    let nak = unsafe { &*nak };\n    let nir = unsafe { &*nir };\n    let fs_key = if fs_key.is_null()'
    replacement='    // macOS embedding: adapt lowered resource ABI before register allocation.\n    if let Some(callback) = embedded_postprocess {\n        unsafe { callback(nir, embedded_data) };\n    }\n'+needle
    assert needle in old;old=old.replace(needle,replacement,1)
    needle='            has_task_shader,\n        )\n    };'
    assert needle in old;old=old.replace(needle,'            has_task_shader,\n            None,\n            std::ptr::null_mut(),\n        )\n    };',1)
    old+='''
// Additional embedding entry point. Existing callers retain the upstream path.
#[no_mangle]
pub extern "C" fn nak_compile_shader_embedded(
    nir: *mut nir_shader,
    dump_asm: bool,
    nak: *const nak_compiler,
    robust2_modes: nir_variable_mode,
    fs_key: *const nak_fs_key,
    has_task_shader: bool,
    callback: Option<unsafe extern "C" fn(*mut nir_shader, *mut core::ffi::c_void)>,
    data: *mut core::ffi::c_void,
) -> *mut nak_shader_bin {
    let compile = || nak_compile_shader_internal(nir, dump_asm, nak, robust2_modes,
                                                fs_key, has_task_shader, callback, data);
    if DEBUG.panic() { compile() }
    else { panic::catch_unwind(compile).unwrap_or(std::ptr::null_mut()) }
}
'''
    return old
edit('src/nouveau/compiler/nak/api.rs','nak_compile_shader_embedded',api)

def binding(old):
    needle='                e.set_field(32..40, idx);\n                e.set_bit(50, false); // .b'
    replacement='''                // macOS bound references pack TIC (8 bits) + TSC (5 bits).
                e.set_field(32..40, idx & 0xff);
                e.set_field(40..45, idx >> 8);
                e.set_bit(50, false); // .b'''
    assert old.count(needle)==6
    return old.replace(needle,replacement)
edit('src/nouveau/compiler/nak/sm20.rs','macOS bound references',binding)

def barriers(old):
    needle='    pub fn visit_instr(&mut self, instr: &Instr) -> Option<u8> {\n        // Flush register reads and writes'
    replacement='''    pub fn visit_instr(&mut self, instr: &Instr) -> Option<u8> {
        // macOS fragment outputs are consumed implicitly by EXIT. Ensure that
        // pending texture results are available even without a final MOV.
        if matches!(instr.op, Op::Exit(_)) && !self.queue_pos.is_empty() {
            self.flush_after(0);
            return Some(0);
        }
        // Flush register reads and writes'''
    assert needle in old;return old.replace(needle,replacement,1)
edit('src/nouveau/compiler/nak/calc_instr_deps.rs','macOS fragment outputs',barriers)

if patches:
    (root/'src/mesa-26.2.4-macos-texture-import.patch').write_text(''.join(patches))
    (root/'results/texture-compiler-patch.json').write_text(json.dumps(records,indent=2)+'\n')
    print('Applied',len(records),'local compiler changes')
else:print('Texture compiler changes already applied')
