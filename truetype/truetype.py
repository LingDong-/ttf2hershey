# -*- coding: utf-8 -*-

# (c) Lingdong Huang 2018

# TrueType specs:
# https://docs.microsoft.com/en-us/typography/opentype/spec
# https://developer.apple.com/fonts/TrueType-Reference-Manual

import numpy as np
import warnings
import os
import math
import ttfparser
import glyphcurves

class TrueTypeFont():
    def __init__(self, path, precision = 0, verbose=True):
        self.precision = precision
        self.verbose = verbose
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.log("reading binary data from "+path+" ...")
        raw = open(path,'rb').read()
        self.cmapCache = {}

        self.log("parsing .ttf file...")
        self.ttf = ttfparser.TTFFile(raw)

        self.log("compiling character map...")
        self.compileCmap()

        self.log("compiling glyphs...")
        self.compileAllGlyphs()

        self.baseline = 0 #self.glyphData[self.chr2idx('x')]['rect'][1]
        self.basewidth = self.glyphData[self.chr2idx('x')]['rect'][2]-\
                 self.glyphData[self.chr2idx('x')]['rect'][0]
        self.log("initialized.")

    def log(self,info):
        if (self.verbose):
            print "["+self.name+"]", info

    def compileCmap(self):
        cmap = self.ttf.tables['cmap']
        offset = cmap['offset']
        self.ttf.file.seek(offset)
        version = self.ttf.file.getUint16()
        numTables = self.ttf.file.getUint16()
        encodingRecords = []

        for i in range(numTables):
            encodingRecords.append({
                "platformID": self.ttf.file.getUint16(),
                "encodingID": self.ttf.file.getUint16(),
                "offset":     self.ttf.file.getUint32(),
            })
        segments = []
        for i in range(len(encodingRecords)):
            self.ttf.file.seek(offset+encodingRecords[i]['offset'])
            _format = self.ttf.file.getUint16()
            if _format != 4 or encodingRecords[i]['platformID'] != 0:
                continue
            length = self.ttf.file.getUint16()
            language = self.ttf.file.getUint16()
            segCountX2 = self.ttf.file.getUint16()
            searchRange = self.ttf.file.getUint16()
            entrySelector = self.ttf.file.getUint16()
            rangeShift = self.ttf.file.getUint16()
            segCount = segCountX2 // 2
            
            for j in range(segCount):
                segments.append({})
            for j in range(segCount):
                segments[j]['endCode'] = self.ttf.file.getUint16()
            reservedPad = self.ttf.file.getUint16()
            for j in range(segCount):
                segments[j]['startCode'] = self.ttf.file.getUint16()
            for j in range(segCount):
                segments[j]['idDelta'] = self.ttf.file.getUint16()
            for j in range(segCount):
                segments[j]['idRangeOffset'] = self.ttf.file.getUint16()
            for i in range(segCount):
                segments[i]['glyphIndexArray'] = self.ttf.file.tell()
            break
        if len(segments) == 0:
            warnings.warn("Unimplemented: Encoding other than (PlatformID = 0, Format = 4) is not yet supported", Warning)
        self.segments = segments

    def chr2idx(self,char):
        try:
            return self.cmapCache[char]
        except KeyError:
            pass
        c = ord(char)
        seg = None
        result = 0
        for s in self.segments:
            if s['startCode'] <= c <= s['endCode']:
                seg = s
                break
        if seg is not None:
            if seg['idRangeOffset'] == 0:
                result = (seg['idDelta']+c) % 65536
            else:
                glyphIndexAddress = (c-seg['startCode'])
                self.ttf.file.seek(seg['glyphIndexArray'])
                for i in range(glyphIndexAddress):
                    self.ttf.file.getUint16()
                result = self.ttf.file.getUint16()

        self.cmapCache[char] = result
        return result

    def compileGlyph (self, index):
        glyph = self.ttf.readGlyph(index);
        bbox = glyph['xMin'], glyph['yMin'], glyph['xMax'], glyph['yMax']
        if (glyph == None):
            warnings.warn("No glyph!", Warning)
            return {"rect":(0,0,1,1), "poly":[]}

        if (glyph["type"] == "simple" ):
            points =  glyph["points"]

            ptlist = []
            for i in range(0,len(glyph["contourEnds"])):
                e0 = (glyph["contourEnds"][i-1]+1) if i != 0 else 0
                e1 = glyph["contourEnds"][i]+1
                ptlist.append(points[e0:e1])

            polylines = []
            for i in range(len(ptlist)):
                if self.precision == 0:
                    polylines.append([])
                    for j in range(len(ptlist[i])):
                        p = ptlist[i][j]
                        polylines[-1].append([p['x'],p['y']])
                else:
                    
                    cc = glyphcurves.construct_curve(ptlist[i],self.precision)
                    polylines.append(cc)
                
        else:
            components = glyph["components"]
            polylines = []
            for c in components:
                subglyf = self.compileGlyph(c['glyphIndex'])['poly']
                xof,yof = 0,0
                xscale, yscale = 1,1
                if c['flags']['ARGS_ARE_XY_VALUES']:
                    xof, yof = c['matrix']['e'], c['matrix']['f']
                else:
                    warnings.warn("Unimplemented: Compound glyphs point matching", Warning)
                if c['flags']['WE_HAVE_A_SCALE'] or c['flags']['WE_HAVE_AN_X_AND_Y_SCALE']:
                    xscale , yscale = c['matrix']['a'], c['matrix']['d']
                if c['flags']['WE_HAVE_A_TWO_BY_TWO']:
                    warnings.warn("Unimplemented: Compound glyphs linear transformation", Warning)

                for i in range(len(subglyf)):
                    try:
                        subglyf[i] = [[xy[0]*xscale+xof, xy[1]*yscale+yof] for xy in subglyf[i]]
                    except:
                        self.log("subglyph failure:")
                        self.log(subglyf)
                        self.log(len(subglyf))
                        self.log(subglyf[i])
                polylines += subglyf

        return {"rect":bbox, "poly":polylines}

    def compileAllGlyphs(self):
        self.glyphData = []
        for i in xrange(self.ttf.length):
            self.glyphData.append(self.compileGlyph(i))


