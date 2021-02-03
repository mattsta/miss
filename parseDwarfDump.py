#!/usr/bin/env python3

import re
import os
import sys
import math
import pprint

from total_size import total_size

sys.setrecursionlimit(65000)

pp = pprint.PrettyPrinter(indent=1)

if False:
    allInput = list(map(str.rstrip, sys.stdin))
else:
    allInput = list(map(str.rstrip, open(sys.argv[1]).readlines()))


everything = []
toplevelMapper = {}


def parseDWARFDUMPIntoLocalPythonDicts():
    def gobble(t, beginning):
        if t.startswith(beginning):
            return t[len(beginning) :]

        return t

    def countDepth(line):
        if " NULL" in line:
            return -2

        if ": " in line:
            try:
                _, maybe = line.split(":")
            except BaseException:
                #            print("Skipping", line)
                return -3

            spacesAndMore = maybe.split("DW")
            spaces = spacesAndMore[0]

            assert spaces == " " * len(spaces)  # verify spaces is all spaces

            # 3 is base depth for top level things and future indents are 2 new
            # spaces for each level
            return int((len(spaces) - 1) / 2)

        return -1

    useDict = everything
    useDict = None
    parents = []
    previousDepth = 0
    for line in allInput:

        # Remove stylistic padding around information we actually want
        # (values are things like: ("filename.c"))
        line = re.sub(r'["()]', "", line)
        currentDepth = countDepth(line)

        # if NULL indicator, return to previous parent
        if currentDepth == -2:
            useDict = parents.pop()
            assert previousDepth > 0
            previousDepth -= 1
        elif currentDepth < 0:
            # This branch adds key-value pairs for a specific 'addr' / 'useDict'
            # intro compile unit stuff
            if (
                "Compile Unit:" in line
                or "file format" in line
                or ".debug_info" in line
            ):
                continue

            # Remove pre/postfix garbage then split on embedded tabs and spaces
            kv = line.strip().split()

            # found a blank line
            if not kv:
                continue

            key = gobble(kv[0], "DW_AT_")
            value = kv[1:]

            key = key.rstrip(":")
            if key.startswith("0x"):
                key = int(key, 16)

            # Split ["0xaddress", "name"] into (int, name)
            if key == "type":
                value = (int(value[0], 16), " ".join(value[1:]))
                # rename inner 'type' to not conflict with top-level 'type'
                key = "atype"
            elif len(value) == 1:
                value = value[0]
                # Convert address to integer
                if value.startswith("0x"):
                    value = int(value, 16)
                else:
                    # Try to convert any other integer strings to integers
                    try:
                        value = int(value)
                    except BaseException:
                        value = gobble(value, "DW_ATE_")
                        pass

            #            print("Setting: k", key, "v:", value)
            assert key not in useDict
            useDict[key] = value
        elif currentDepth >= 0:
            try:
                addr, rest = line.split(":")
                _spaces, thingIs = rest.split("DW_TAG_")
            except BaseException:
                #                print("Skipping", line)
                continue

            addr = int(addr, 16)
            #            print(f"OPENING for 0x{addr:x}, {line}!")

            # If at root, use top level dict for 'addr' storage
            if currentDepth > previousDepth:
                #                print("ENTERING DEPTH   ", line, previousDepth, currentDepth)
                assert len(parents) == previousDepth
                parents.append(useDict)
                useDict = useDict["children"]
            elif currentDepth < previousDepth:
                #                print("LEAVING DEPTH    ", line, previousDepth, currentDepth)
                assert len(parents) == currentDepth
                useDict = useDict["children"]
            elif currentDepth == previousDepth:
                #                print("KEEPING DEPTH FOR", line, currentDepth)
                if parents:
                    useDict = parents[-1]["children"]
                else:
                    useDict = everything

            assert addr not in useDict
            assert addr not in toplevelMapper

            detailDict = {"type": thingIs, "children": []}
            useDict.append(detailDict)
            toplevelMapper[addr] = detailDict

            useDict = detailDict
            previousDepth = currentDepth

    assert not parents


def removeEmptyChildren(koala):
    for v in koala:
        if "children" in v:
            if len(v["children"]) == 0:
                del v["children"]
            else:
                removeEmptyChildren(v["children"])


def resolveTypeBytes(t):
    ut = toplevelMapper[t]

    # TODO: extract addr_size from input for dynamic pointer sizes
    if ut["type"] == "pointer_type":
        return 8

    if "byte_size" in ut:
        return ut["byte_size"]

    # Things like:
    # 0x00002e67:   DW_TAG_array_type
    #                 DW_AT_type  (0x00002e0c "...")
    #
    # 0x00002e6c:     DW_TAG_subrange_type
    #                   DW_AT_type    (0x000023b4 "__ARRAY_SIZE_TYPE__")
    #                   DW_AT_count   (0x00)
    if "children" in ut:
        #        print("UT", ut)
        foundAType = ut["atype"][0] if "atype" in ut else None
        foundCount = None
        foundSize = None
        for vv in ut["children"]:
            assert isinstance(vv, dict)
            k = vv["type"]
            if k == "typedef":
                pass
            elif k == "array_type":
                pass
            elif k == "subprogram":
                pass
            elif k == "structure_type":
                pass
            elif k == "enumeration_type":
                pass
            elif k == "restrict_type":
                pass
            elif k == "const_type":
                pass
            elif k == "variable":
                pass
            elif k == "pointer_type":
                pass
            elif k == "base_type":
                foundSize = None  # vv['byte_size']
            elif k == "subrange_type":
                if "count" not in vv:
                    foundCount = 0
                else:
                    foundCount = vv["count"]
            else:
                assert None, f"unexpected type of sub size finding? ({k})"

        assert (foundSize or foundAType) and foundCount is not None

        if foundSize:
            print("Custom size:", foundCount, foundSize)
            return foundCount * foundSize

        #        print("Iterating for next size with count", foundCount, foundAType)
        return foundCount * resolveTypeBytes(foundAType)

    return resolveTypeBytes(ut["atype"][0])


processed = set()


def findStructsInChildren(pineapple, depth=1):
    vv = pineapple

    for v in vv:
        if not isinstance(v, dict):
            continue

        if "type" not in v:
            continue

        # Abstract name creation, no details provided here
        if "declaration" in v:
            continue

        #        print(f"Found {k}: {v['type']} (length {len(v)})!")
        if "children" in v:
            if v["type"] == "compile_unit":
                findStructsInChildren(v["children"])
            elif v["type"] == "structure_type":
                # Iterate children!
                if "name" in v:
                    # A single dwarfdump output can have _multiple_ compile
                    # unit/file results inside of it, so we can end up with
                    # _MULTIPLE_ struct definitions. Assume all our structs at
                    # the same and only print them the first time we see them.
                    structName = v["name"]
                    if structName in processed:
                        continue
                    else:
                        processed.add(structName)

                    print(structName)

                totalSize = 0
                totalSizeUsed = v["byte_size"]

                for desc in v["children"]:
                    if "data_member_location" in desc:
                        name = desc["name"]

                        if "decl_file" in desc:
                            filenameItself = os.path.basename(desc["decl_file"])
                            lineItself = desc["decl_line"]
                        else:
                            filenameItself = "?"
                            lineItself = "?"
                        sizeItself = desc["data_member_location"]
                        typeDesc = desc["atype"][1]
                        typeSize = resolveTypeBytes(desc["atype"][0])
                        totalSize += typeSize

                        if not isinstance(sizeItself, int):
                            sizeItself = "?"

                        print(
                            f"{sizeItself:{depth * 8}} {filenameItself}:{lineItself} {name} ({typeSize}) ({typeDesc})"
                        )
                #                        findStructsInChildren(desc, depth + 1)

                totalSizeCacheLines = totalSize / 64
                totalSizeUsedCacheLines = totalSizeUsed / 64
                print(f"Length: {totalSize} ({totalSizeCacheLines} cache lines)")

                if totalSize != totalSizeUsed:
                    print(
                        f"But deployed with padding: {totalSizeUsed} ({totalSizeUsedCacheLines} cache lines)"
                    )

                    if totalSize:
                        print(
                            f"Optimal would require removing: {totalSizeUsed - totalSize} bytes"
                        )

                        if (
                            int(totalSizeCacheLines) != int(totalSizeUsedCacheLines)
                        ) and math.ceil(totalSizeCacheLines) < math.ceil(
                            totalSizeUsedCacheLines
                        ):
                            print(f"FIXME: reordering can use fewer cache lines!")

                if (totalSizeUsed / 64) > (32768 / 64):
                    print("What are you doing blowing out your entire L1 cache?")

                assert totalSizeUsed >= totalSize

                print()

            if "children" in v:
                findStructsInChildren(v, depth + 1)


parseDWARFDUMPIntoLocalPythonDicts()


print(f"Compile units: {len(everything)}")
total = total_size(everything)
totalIdx = total_size(toplevelMapper)
print(f"Python memory usage for representation is this big: {total:,} bytes ({total / 1024 / 1024:,.2f} MB)")
print(
    f"This big (as reference): {totalIdx:,} bytes ({totalIdx / 1024 / 1024:,.2f} MB)"
)
removeEmptyChildren(everything)
# pp.pprint(everything)
findStructsInChildren(everything)
