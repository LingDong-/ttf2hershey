# TrueType font file parser
# Lingdong Huang 2018
# based on js from: http://stevehanov.ca/blog/index.php?id=143

import numpy as np
import struct


class BinaryReader():
    def __init__(this,arrayBuffer):
        this.pos = 0
        this.data = [struct.unpack('B', x)[0] for x in arrayBuffer]

    def seek(this, pos):
        assert(pos >=0 and pos <= len(this.data))
        oldPos = this.pos
        this.pos = pos
        return oldPos
    
    def tell(this):
        return this.pos;

    def getUint8(this):
        assert(this.pos < len(this.data));
        this.pos += 1
        return this.data[this.pos-1];

    def getUint16(this):
        return ((this.getUint8() << 8) | this.getUint8()) >> 0;

    def getUint32(this):
       return this.getInt32() >> 0;

    def getInt16(this):
        result = this.getUint16();
        if (result & 0x8000):
            result -= (1 << 16);
        return result;

    def getInt32(this):
        return ((this.getUint8() << 24) | 
                (this.getUint8() << 16) |
                (this.getUint8() <<  8) |
                (this.getUint8()      ));

    def getFword(this):
        return this.getInt16();

    def get2Dot14(this):
        return this.getInt16() / (1 << 14);
    

    def getFixed(this):
        return this.getInt32() / (1 << 16);

    def getString(this,length):
        result = "";
        for i in xrange(length):
            result += chr(this.getUint8());
        return result

    def getDate(this):
        macTime = this.getUint32() * 0x100000000 + this.getUint32();
        return macTime


class TTFFile():
    def __init__(this, arrayBuffer):
        this.file = BinaryReader(arrayBuffer);
        this.tables = this.readOffsetTables(this.file);
        this.readHeadTable(this.file);
        this.length = this.glyphCount();


    def readOffsetTables(this, file):
        tables = {};
        this.scalarType = file.getUint32();
        numTables = file.getUint16();
        this.searchRange = file.getUint16();
        this.entrySelector = file.getUint16();
        this.rangeShift = file.getUint16();

        for i in xrange(numTables):
            tag = file.getString(4);
            tables[tag] = {
                "checksum": file.getUint32(),
                "offset": file.getUint32(),
                "length": file.getUint32()
            };

            if (tag != 'head'):

                assert(this.calculateTableChecksum(file, tables[tag]["offset"],
                            tables[tag]["length"]) == tables[tag]["checksum"]);

            
        return tables

    def calculateTableChecksum(this, file, offset, length):

        old = file.seek(offset);
        _sum = 0;
        nlongs = ((length + 3) / 4) | 0;
        while ( nlongs > 0 ):
            nlongs -= 1
            _sum = (_sum + file.getUint32() & 0xffffffff) >> 0;

        file.seek(old);
        return _sum;

    def readHeadTable(this,file):
        assert("head" in this.tables);
        file.seek(this.tables["head"]["offset"]);

        this.version = file.getFixed();
        this.fontRevision = file.getFixed();
        this.checksumAdjustment = file.getUint32();
        this.magicNumber = file.getUint32();
        assert(this.magicNumber == 0x5f0f3cf5);
        this.flags = file.getUint16();
        this.unitsPerEm = file.getUint16();
        this.created = file.getDate();
        this.modified = file.getDate();
        this.xMin = file.getFword();
        this.yMin = file.getFword();
        this.xMax = file.getFword();
        this.yMax = file.getFword();
        this.macStyle = file.getUint16();
        this.lowestRecPPEM = file.getUint16();
        this.fontDirectionHint = file.getInt16();
        this.indexToLocFormat = file.getInt16();
        this.glyphDataFormat = file.getInt16();

    def glyphCount(this):
        assert("maxp" in this.tables);
        old = this.file.seek(this.tables["maxp"]["offset"] + 4);
        count = this.file.getUint16();
        this.file.seek(old);
        return count;


    def getGlyphOffset(this,index):
        assert("loca" in this.tables);
        table = this.tables["loca"];
        file = this.file;
        offset, old = 0, 0

        if (this.indexToLocFormat == 1):
            old = file.seek(table["offset"] + index * 4);
            offset = file.getUint32();
        else:
            old = file.seek(table["offset"] + index * 2);
            offset = file.getUint16() * 2;

        file.seek(old);
        return offset + this.tables["glyf"]["offset"];


    def readGlyph(this, index):
        offset = this.getGlyphOffset(index);
        file = this.file;

        if (offset >= this.tables["glyf"]["offset"] + this.tables["glyf"]["length"]):
            return None

        assert(offset >= this.tables["glyf"]["offset"]);
        assert(offset < this.tables["glyf"]["offset"] + this.tables["glyf"]["length"]);

        file.seek(offset);

        glyph = {
            "numberOfContours": file.getInt16(),
            "xMin": file.getFword(),
            "yMin": file.getFword(),
            "xMax": file.getFword(),
            "yMax": file.getFword()
        };

        assert(glyph["numberOfContours"] >= -1);

        if (glyph["numberOfContours"] == -1):
            this.readCompoundGlyph(file, glyph);
        else:
            this.readSimpleGlyph(file, glyph);

        return glyph;

    def readSimpleGlyph(this, file, glyph):

        ON_CURVE        =  1
        X_IS_BYTE       =  2
        Y_IS_BYTE       =  4
        REPEAT          =  8
        X_DELTA         = 16
        Y_DELTA         = 32

        glyph["type"] = "simple";
        glyph["contourEnds"] = [];
        points = glyph["points"] = [];

        for i in xrange(0, glyph["numberOfContours"]):
            glyph["contourEnds"].append(file.getUint16());

        # skip over intructions
        file.seek(file.getUint16() + file.tell());

        if (glyph["numberOfContours"] == 0):
            return;

        numPoints = max(glyph["contourEnds"]) + 1;

        flags = [];

        i = 0
        while (i < numPoints):
            flag = file.getUint8();
            flags.append(flag);
            points.append({
                "onCurve": (flag & ON_CURVE) > 0
            });

            if ( flag & REPEAT ):
                repeatCount = file.getUint8();
                assert(repeatCount > 0);
                i += repeatCount;
                while( repeatCount > 0):
                    repeatCount -= 1
                    flags.append(flag);
                    points.append({
                        "onCurve": (flag & ON_CURVE) > 0
                    })
            i += 1

        def readCoords(name, byteFlag, deltaFlag, min, max):
            value = 0;

            for i in xrange(numPoints):
                flag = flags[i];
                if ( flag & byteFlag ):
                    if ( flag & deltaFlag ):
                        value += file.getUint8();
                    else:
                        value -= file.getUint8();
                elif ( (~flag) & deltaFlag ):
                    value += file.getInt16()
                else:
                    pass
                    # value is unchanged.
                points[i][name] = value;
            
        readCoords("x", X_IS_BYTE, X_DELTA, glyph["xMin"], glyph["xMax"]);
        readCoords("y", Y_IS_BYTE, Y_DELTA, glyph["yMin"], glyph["yMax"]);

    def readCompoundGlyph(this, file, glyph):
        ARG_1_AND_2_ARE_WORDS    = 1
        ARGS_ARE_XY_VALUES       = 2
        ROUND_XY_TO_GRID         = 4
        WE_HAVE_A_SCALE          = 8
        # RESERVED              = 16
        MORE_COMPONENTS          = 32
        WE_HAVE_AN_X_AND_Y_SCALE = 64
        WE_HAVE_A_TWO_BY_TWO     = 128
        WE_HAVE_INSTRUCTIONS     = 256
        USE_MY_METRICS           = 512
        OVERLAP_COMPONENT        = 1024

        glyph["type"] = "compound";
        glyph["components"] = [];

        flags = MORE_COMPONENTS;
        while( flags & MORE_COMPONENTS ):
            arg1, arg2 = 0, 0

            flags = file.getUint16();
            component = {
                "glyphIndex": file.getUint16(),
                "matrix": {
                    'a': 1, 'b': 0, 'c': 0, 'd': 1, 'e': 0, 'f': 0
                },
                "flags":{
                    "ARGS_ARE_XY_VALUES": bool(flags & ARGS_ARE_XY_VALUES),
                    "WE_HAVE_A_SCALE": bool(flags & WE_HAVE_A_SCALE),
                    "WE_HAVE_AN_X_AND_Y_SCALE": bool(flags & WE_HAVE_AN_X_AND_Y_SCALE),
                    "WE_HAVE_A_TWO_BY_TWO": bool(flags & WE_HAVE_A_TWO_BY_TWO),
                }
            };

            if ( flags & ARG_1_AND_2_ARE_WORDS ):
                arg1 = file.getInt16();
                arg2 = file.getInt16();
            else:
                arg1 = file.getUint8();
                arg2 = file.getUint8();

            if ( flags & ARGS_ARE_XY_VALUES ):
                component["matrix"]["e"] = arg1;
                component["matrix"]["f"] = arg2;
            else:
                component.destPointIndex = arg1;
                component.srcPointIndex = arg2;

            if ( flags & WE_HAVE_A_SCALE ):
                component["matrix"]['a'] = file.get2Dot14();
                component["matrix"]['d'] = component["matrix"]['a'];
            elif ( flags & WE_HAVE_AN_X_AND_Y_SCALE ):
                component["matrix"]['a'] = file.get2Dot14();
                component["matrix"]['d'] = file.get2Dot14();
            elif ( flags & WE_HAVE_A_TWO_BY_TWO ):
                component["matrix"]['a'] = file.get2Dot14();
                component["matrix"]['b'] = file.get2Dot14();
                component["matrix"]['c'] = file.get2Dot14();
                component["matrix"]['d'] = file.get2Dot14();
            glyph["components"].append(component);
        #print glyph["components"]
        if ( flags & WE_HAVE_INSTRUCTIONS ):
            file.seek(file.getUint16() + file.tell());


            