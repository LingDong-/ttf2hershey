# -*- coding: utf-8 -*-

# parse glyphs as curves
# (c) Lingdong Huang 2018

def lerp(p0,p1,t):
    x = (1-t) * p0[0] + t * p1[0]
    y = (1-t) * p0[1] + t * p1[1]
    return [x,y]

def high_bezier(pts,t):
    if len(pts) == 1:
        return pts[0]
    elif len(pts) == 2:
        return lerp(pts[0],pts[1],t)
    else:
        return lerp(high_bezier(pts[:-1], t), high_bezier(pts[1:], t), t)

def construct_curve(pts, precision=10, maxhandle=5):
    buff = []
    curve = []
    def flush():
        n = precision*len(buff)
        for j in range(0,n):
            t = float(j)/float(n)
            curve.append(high_bezier(buff,t))

    for i in range(len(pts)):
        x,y = pts[i]['x'], pts[i]['y']
        buff.append([x,y])

        if pts[i]['onCurve']:
            if 1 < len(buff) <= maxhandle+2:
                flush()
                buff = [[x,y]]
            else:
                curve += buff
                buff = []
        elif i == 0:
            buff = [[pts[-1]['x'],pts[-1]['y']]]+buff
        elif i == len(pts)-1:
            buff += [[pts[0]['x'],pts[0]['y']]]
            if 1 < len(buff) <= maxhandle+2:
                flush()
            else:
                curve += buff
            buff = []
    curve += buff
    curve = [[c[0],c[1]] for c in curve]

    return curve
