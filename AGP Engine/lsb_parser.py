#!/usr/bin/env python3
"""
LSB文件解析工具 - 提取并解析PipelineLayout

LSB文件格式:
- Header (14 bytes):
  - tag: 'rfl' + version (4 bytes)
  - type: shader stage flags (2 bytes, uint16)
  - offsetPushConstants (2 bytes, uint16)
  - offsetSpecializationConstants (2 bytes, uint16)
  - offsetDescriptorSets (2 bytes, uint16)
  - offsetInputs (2 bytes, uint16)
  - offsetLocalSize (2 bytes, uint16)

DescriptorType枚举:
  0: SAMPLER
  1: COMBINED_IMAGE_SAMPLER
  2: SAMPLED_IMAGE
  3: STORAGE_IMAGE
  4: UNIFORM_TEXEL_BUFFER
  5: STORAGE_TEXEL_BUFFER
  6: UNIFORM_BUFFER
  7: STORAGE_BUFFER
  8: UNIFORM_BUFFER_DYNAMIC
  9: STORAGE_BUFFER_DYNAMIC
 10: INPUT_ATTACHMENT
 1000150000: ACCELERATION_STRUCTURE

ShaderStageFlags:
  0x00000001: VERTEX_BIT
  0x00000010: FRAGMENT_BIT
  0x00000020: COMPUTE_BIT
  0x0000001F: ALL_GRAPHICS
  0x7FFFFFFF: ALL

AdditionalDescriptorTypeFlags:
  0x00000001: IMAGE_DEPTH_BIT
  0x00000002: IMAGE_ARRAY_BIT
  0x00000004: IMAGE_MULTISAMPLE_BIT
  0x00000008: IMAGE_SAMPLED_BIT
  0x00000010: IMAGE_LOAD_STORE_BIT
  0x00010000: IMAGE_DIMENSION_1D_BIT
  0x00020000: IMAGE_DIMENSION_2D_BIT
  0x00040000: IMAGE_DIMENSION_3D_BIT
  0x00080000: IMAGE_DIMENSION_CUBE_BIT
  0x00100000: IMAGE_DIMENSION_BUFFER_BIT
  0x00200000: IMAGE_DIMENSION_SUBPASS_BIT
"""

import struct
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

# DescriptorType枚举名称映射
DESCRIPTOR_TYPE_NAMES = {
    0: "SAMPLER",
    1: "COMBINED_IMAGE_SAMPLER",
    2: "SAMPLED_IMAGE",
    3: "STORAGE_IMAGE",
    4: "UNIFORM_TEXEL_BUFFER",
    5: "STORAGE_TEXEL_BUFFER",
    6: "UNIFORM_BUFFER",
    7: "STORAGE_BUFFER",
    8: "UNIFORM_BUFFER_DYNAMIC",
    9: "STORAGE_BUFFER_DYNAMIC",
    10: "INPUT_ATTACHMENT",
    1000150000: "ACCELERATION_STRUCTURE",
}

# ShaderStageFlags名称映射
SHADER_STAGE_NAMES = {
    0x00000001: "VERTEX_BIT",
    0x00000010: "FRAGMENT_BIT",
    0x00000020: "COMPUTE_BIT",
    0x0000001F: "ALL_GRAPHICS",
    0x7FFFFFFF: "ALL",
}

# AdditionalDescriptorTypeFlags名称映射
ADDITIONAL_FLAG_NAMES = {
    0x00000001: "IMAGE_DEPTH",
    0x00000002: "IMAGE_ARRAY",
    0x00000004: "IMAGE_MULTISAMPLE",
    0x00000008: "IMAGE_SAMPLED",
    0x00000010: "IMAGE_LOAD_STORE",
    0x00010000: "DIMENSION_1D",
    0x00020000: "DIMENSION_2D",
    0x00040000: "DIMENSION_3D",
    0x00080000: "DIMENSION_CUBE",
    0x00100000: "DIMENSION_BUFFER",
    0x00200000: "DIMENSION_SUBPASS",
}

# ImageDimension枚举
IMAGE_DIMENSION_NAMES = {
    0: "DIMENSION_RECT",
    1: "DIMENSION_1D",
    2: "DIMENSION_2D",
    3: "DIMENSION_3D",
    4: "DIMENSION_CUBE",
    5: "DIMENSION_BUFFER",
    6: "DIMENSION_SUBPASS",
}


@dataclass
class DescriptorSetLayoutBinding:
    binding: int
    descriptor_type: str
    descriptor_type_value: int
    descriptor_count: int
    shader_stage_flags: str
    shader_stage_flags_value: int
    additional_flags: List[str] = field(default_factory=list)
    additional_flags_value: int = 0
    image_dimension: Optional[str] = None
    image_flags: List[str] = field(default_factory=list)


@dataclass
class DescriptorSetLayout:
    set: int
    bindings: List[DescriptorSetLayoutBinding] = field(default_factory=list)


@dataclass
class PushConstant:
    shader_stage_flags: str
    shader_stage_flags_value: int
    byte_size: int


@dataclass
class SpecializationConstant:
    shader_stage: str
    shader_stage_value: int
    id: int
    type: str
    type_value: int


@dataclass
class VertexInput:
    location: int
    format_value: int
    binding: int = 0
    offset: int = 0


@dataclass
class LocalSize:
    x: int = 1
    y: int = 1
    z: int = 1


@dataclass
class PipelineLayout:
    shader_stage: str
    shader_stage_value: int
    version: int
    push_constant: Optional[PushConstant] = None
    descriptor_sets: List[DescriptorSetLayout] = field(default_factory=list)
    specialization_constants: List[SpecializationConstant] = field(default_factory=list)
    vertex_inputs: List[VertexInput] = field(default_factory=list)
    local_size: Optional[LocalSize] = None


def read_uint8(data: bytes, offset: int) -> Tuple[int, int]:
    value = data[offset]
    return value, offset + 1


def read_uint16(data: bytes, offset: int) -> Tuple[int, int]:
    value = struct.unpack_from("<H", data, offset)[0]
    return value, offset + 2


def read_uint32(data: bytes, offset: int) -> Tuple[int, int]:
    value = struct.unpack_from("<I", data, offset)[0]
    return value, offset + 4


def get_shader_stage_name(flags: int) -> str:
    names = []
    for flag, name in SHADER_STAGE_NAMES.items():
        if flags & flag:
            names.append(name)
    if not names:
        return "UNKNOWN"
    return "|".join(names)


def get_descriptor_type_name(type_val: int) -> str:
    if type_val in DESCRIPTOR_TYPE_NAMES:
        return DESCRIPTOR_TYPE_NAMES[type_val]
    # 处理ACCELERATION_STRUCTURE的特殊情况（可能被截断为16位）
    if type_val == (1000150000 & 0xFFFF):
        return "ACCELERATION_STRUCTURE"
    return f"UNKNOWN({type_val})"


def get_additional_flags_names(flags: int) -> Tuple[List[str], Optional[str], List[str]]:
    flag_names = []
    dimension = None
    image_flag_names = []

    for flag, name in ADDITIONAL_FLAG_NAMES.items():
        if flags & flag:
            if "DIMENSION" in name:
                dimension = name
            elif "IMAGE" in name and "DIMENSION" not in name:
                image_flag_names.append(name)
            flag_names.append(name)

    return flag_names, dimension, image_flag_names


def parse_lsb_file(file_path: str) -> Optional[PipelineLayout]:
    """解析LSB文件并返回PipelineLayout"""

    with open(file_path, "rb") as f:
        data = f.read()

    if len(data) < 14:
        print(f"Error: File too small ({len(data)} bytes), minimum 14 bytes for header")
        return None

    # 解析Header
    tag = data[0:3].decode("ascii", errors="replace")
    version = data[3]

    if tag != "rfl":
        print(f"Error: Invalid tag '{tag}', expected 'rfl'")
        return None

    if version not in (0, 1):
        print(f"Error: Invalid version {version}, expected 0 or 1")
        return None

    shader_stage_value, offset = read_uint16(data, 4)
    offset_push_constants = struct.unpack_from("<H", data, 6)[0]
    offset_specialization_constants = struct.unpack_from("<H", data, 8)[0]
    offset_descriptor_sets = struct.unpack_from("<H", data, 10)[0]
    offset_inputs = struct.unpack_from("<H", data, 12)[0]
    offset_local_size = struct.unpack_from("<H", data, 14)[0]

    shader_stage = get_shader_stage_name(shader_stage_value)

    pipeline_layout = PipelineLayout(
        shader_stage=shader_stage,
        shader_stage_value=shader_stage_value,
        version=version,
    )

    # 计算各段大小
    offsets = [
        offset_push_constants,
        offset_specialization_constants,
        offset_descriptor_sets,
        offset_inputs,
        offset_local_size,
    ]
    offsets_sorted = sorted([(o, i) for i, o in enumerate(offsets) if o > 0])

    sizes = [0] * 5
    for idx, (o, i) in enumerate(offsets_sorted):
        if idx < len(offsets_sorted) - 1:
            next_offset = offsets_sorted[idx + 1][0]
            sizes[i] = next_offset - o
        else:
            sizes[i] = len(data) - o

    # 解析PushConstants
    if offset_push_constants > 0 and sizes[0] >= 3:
        ptr = offset_push_constants
        has_constants, ptr = read_uint8(data, ptr)
        if has_constants:
            byte_size, ptr = read_uint16(data, ptr)
            pipeline_layout.push_constant = PushConstant(
                shader_stage_flags=shader_stage,
                shader_stage_flags_value=shader_stage_value,
                byte_size=byte_size,
            )

    # 解析DescriptorSets
    if offset_descriptor_sets > 0 and sizes[2] >= 2:
        ptr = offset_descriptor_sets
        descriptor_set_count, ptr = read_uint16(data, ptr)

        for _ in range(descriptor_set_count):
            if ptr + 4 > len(data):
                break

            set_idx, ptr = read_uint16(data, ptr)
            binding_count, ptr = read_uint16(data, ptr)

            if set_idx >= 4:  # MAX_DESCRIPTOR_SET_COUNT
                print(f"Warning: Invalid set index {set_idx}")
                continue

            descriptor_set = DescriptorSetLayout(set=set_idx)

            for _ in range(binding_count):
                if version == 0:
                    # V0: 3 x uint16 (binding, type, count)
                    if ptr + 6 > len(data):
                        break
                    binding, ptr = read_uint16(data, ptr)
                    desc_type_val, ptr = read_uint16(data, ptr)
                    desc_count, ptr = read_uint16(data, ptr)
                    additional_flags_val = 0
                else:
                    # V1: 3 x uint16 + 2 x uint8 (binding, type, count, imageDim, imageFlags)
                    if ptr + 8 > len(data):
                        break
                    binding, ptr = read_uint16(data, ptr)
                    desc_type_val, ptr = read_uint16(data, ptr)
                    desc_count, ptr = read_uint16(data, ptr)
                    image_dim_val, ptr = read_uint8(data, ptr)
                    image_flags_val, ptr = read_uint8(data, ptr)

                    # 构造additional flags
                    additional_flags_val = 0
                    if image_dim_val <= 6:
                        dim_flag = 0x00010000 << image_dim_val if image_dim_val > 0 else 0
                        if image_dim_val == 2:
                            dim_flag = 0x00020000
                        additional_flags_val |= dim_flag
                    additional_flags_val |= image_flags_val

                # 处理ACCELERATION_STRUCTURE的特殊情况
                if desc_type_val > 10 and desc_type_val == (1000150000 & 0xFFFF):
                    desc_type_val = 1000150000

                flag_names, dimension, image_flag_names = get_additional_flags_names(additional_flags_val)

                binding_obj = DescriptorSetLayoutBinding(
                    binding=binding,
                    descriptor_type=get_descriptor_type_name(desc_type_val),
                    descriptor_type_value=desc_type_val,
                    descriptor_count=desc_count,
                    shader_stage_flags=shader_stage,
                    shader_stage_flags_value=shader_stage_value,
                    additional_flags=flag_names,
                    additional_flags_value=additional_flags_val,
                    image_dimension=dimension,
                    image_flags=image_flag_names,
                )

                descriptor_set.bindings.append(binding_obj)

            pipeline_layout.descriptor_sets.append(descriptor_set)

    # 解析SpecializationConstants
    if offset_specialization_constants > 0 and sizes[1] >= 4:
        ptr = offset_specialization_constants
        const_count, ptr = read_uint32(data, ptr)

        type_names = {0: "INVALID", 1: "BOOL", 2: "UINT32", 3: "INT32", 4: "FLOAT"}

        for _ in range(const_count):
            if ptr + 8 > len(data):
                break
            const_id, ptr = read_uint32(data, ptr)
            const_type_val, ptr = read_uint32(data, ptr)

            spec_const = SpecializationConstant(
                shader_stage=shader_stage,
                shader_stage_value=shader_stage_value,
                id=const_id,
                type=type_names.get(const_type_val, f"UNKNOWN({const_type_val})"),
                type_value=const_type_val,
            )
            pipeline_layout.specialization_constants.append(spec_const)

    # 解析VertexInputs
    if offset_inputs > 0 and sizes[3] >= 2:
        ptr = offset_inputs
        input_count, ptr = read_uint16(data, ptr)

        for _ in range(input_count):
            if ptr + 4 > len(data):
                break
            location, ptr = read_uint16(data, ptr)
            format_val, ptr = read_uint16(data, ptr)

            vertex_input = VertexInput(
                location=location,
                format_value=format_val,
                binding=location,
                offset=0,
            )
            pipeline_layout.vertex_inputs.append(vertex_input)

    # 解析LocalSize (for compute shaders)
    if offset_local_size > 0 and sizes[4] >= 12:
        ptr = offset_local_size
        x, ptr = read_uint32(data, ptr)
        y, ptr = read_uint32(data, ptr)
        z, ptr = read_uint32(data, ptr)

        pipeline_layout.local_size = LocalSize(x=x, y=y, z=z)

    return pipeline_layout


def pipeline_layout_to_dict(pl: PipelineLayout) -> Dict[str, Any]:
    """将PipelineLayout转换为字典格式"""
    result = {
        "shader_stage": pl.shader_stage,
        "shader_stage_value": pl.shader_stage_value,
        "version": pl.version,
    }

    if pl.push_constant:
        result["push_constant"] = {
            "shader_stage_flags": pl.push_constant.shader_stage_flags,
            "shader_stage_flags_value": pl.push_constant.shader_stage_flags_value,
            "byte_size": pl.push_constant.byte_size,
        }

    if pl.descriptor_sets:
        result["descriptor_sets"] = []
        for ds in pl.descriptor_sets:
            ds_dict = {
                "set": ds.set,
                "bindings": [],
            }
            for b in ds.bindings:
                binding_dict = {
                    "binding": b.binding,
                    "descriptor_type": b.descriptor_type,
                    "descriptor_type_value": b.descriptor_type_value,
                    "descriptor_count": b.descriptor_count,
                    "shader_stage_flags": b.shader_stage_flags,
                    "shader_stage_flags_value": b.shader_stage_flags_value,
                }
                if b.additional_flags:
                    binding_dict["additional_flags"] = b.additional_flags
                    binding_dict["additional_flags_value"] = b.additional_flags_value
                if b.image_dimension:
                    binding_dict["image_dimension"] = b.image_dimension
                if b.image_flags:
                    binding_dict["image_flags"] = b.image_flags
                ds_dict["bindings"].append(binding_dict)
            result["descriptor_sets"].append(ds_dict)

    if pl.specialization_constants:
        result["specialization_constants"] = []
        for sc in pl.specialization_constants:
            result["specialization_constants"].append({
                "shader_stage": sc.shader_stage,
                "shader_stage_value": sc.shader_stage_value,
                "id": sc.id,
                "type": sc.type,
                "type_value": sc.type_value,
            })

    if pl.vertex_inputs:
        result["vertex_inputs"] = []
        for vi in pl.vertex_inputs:
            result["vertex_inputs"].append({
                "location": vi.location,
                "format_value": vi.format_value,
                "binding": vi.binding,
                "offset": vi.offset,
            })

    if pl.local_size:
        result["local_size"] = {
            "x": pl.local_size.x,
            "y": pl.local_size.y,
            "z": pl.local_size.z,
        }

    return result


def print_pipeline_layout(pl: PipelineLayout, indent: int = 0):
    """以树形格式打印PipelineLayout"""
    prefix = "  " * indent

    print(f"{prefix}PipelineLayout:")
    print(f"{prefix}  Shader Stage: {pl.shader_stage} (0x{pl.shader_stage_value:08X})")
    print(f"{prefix}  Version: {pl.version}")

    if pl.push_constant:
        print(f"{prefix}  Push Constant:")
        print(f"{prefix}    Byte Size: {pl.push_constant.byte_size}")

    if pl.descriptor_sets:
        print(f"{prefix}  Descriptor Sets:")
        for ds in pl.descriptor_sets:
            print(f"{prefix}    Set {ds.set}:")
            for b in ds.bindings:
                flags_str = ""
                if b.additional_flags:
                    flags_str = f" [{', '.join(b.additional_flags)}]"
                print(f"{prefix}      Binding {b.binding}: {b.descriptor_type} "
                      f"(count={b.descriptor_count}){flags_str}")

    if pl.specialization_constants:
        print(f"{prefix}  Specialization Constants:")
        for sc in pl.specialization_constants:
            print(f"{prefix}    ID {sc.id}: {sc.type}")

    if pl.vertex_inputs:
        print(f"{prefix}  Vertex Inputs:")
        for vi in pl.vertex_inputs:
            print(f"{prefix}    Location {vi.location}: format=0x{vi.format_value:04X}")

    if pl.local_size:
        print(f"{prefix}  Local Size: ({pl.local_size.x}, {pl.local_size.y}, {pl.local_size.z})")


def main():
    if len(sys.argv) < 2:
        print("用法: python lsb_parser.py <lsb文件路径> [--json] [--output <输出文件>]")
        print("选项:")
        print("  --json       以JSON格式输出")
        print("  --output     指定输出文件路径")
        print("  --all        搜索并解析当前目录下所有.lsb文件")
        sys.exit(1)

    output_json = False
    output_file = None
    parse_all = False
    input_files = []

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--json":
            output_json = True
        elif arg == "--output":
            if i + 1 < len(args):
                output_file = args[i + 1]
                i += 1
        elif arg == "--all":
            parse_all = True
        else:
            input_files.append(arg)
        i += 1

    if parse_all:
        # 搜索所有.lsb文件
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(".lsb"):
                    input_files.append(os.path.join(root, file))

    if not input_files:
        print("错误: 没有找到.lsb文件")
        sys.exit(1)

    results = {}
    for file_path in input_files:
        print(f"\n解析: {file_path}")
        print("-" * 60)

        pl = parse_lsb_file(file_path)
        if pl:
            if output_json:
                pl_dict = pipeline_layout_to_dict(pl)
                results[file_path] = pl_dict
                print(json.dumps(pl_dict, indent=2, ensure_ascii=False))
            else:
                print_pipeline_layout(pl)

    if output_file and results:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    main()