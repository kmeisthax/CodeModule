"""Implementation of Malias Compression for CodeModule
    
Malias Compression is a terribly predictable encoding of LZ77 used in the first
Keitai Denjuu Telefang game (both Speed and Power) for Game Boy Color."""

def compress(data):
    """All-at-once Malias encoder"""
    
    outsize = len(data) #max length 64K
    
    windowstart = -0x7FF #first byte that can be referenced in a Copy command
    windowend = 34 #last byte we can copy with RLE
    
    curbyte = 0 #the byte we are currently working on encoding
    
    encoded = [b'\x01']
    
    encoded.append(bytes(chr(outsize      & 0xFF), "raw_unicode_escape"))
    encoded.append(bytes(chr(outsize >> 8 & 0xFF), "raw_unicode_escape"))
    
    bytesleft = outsize
    
    bundlecmds = []
    operands_encoded = []
    while bytesleft > 0:
        #linear search through the window for references
        #not very efficient, sosumi
        record = 0
        recordstart = -1
        
        curmatchlen = 0
        curmatchstart = -1
        
        matchpos = 0
            
        for searchidx in range(max(0, windowstart), curbyte):
            if data[searchidx] == data[curbyte + matchpos]:
                if curmatchstart + curmatchlen == searchidx:
                    #continuing current match
                    matchpos += 1
                    curmatchlen += 1
                else:
                    #new match
                    curmatchlen = 1
                    curmatchstart = searchidx
            else:
                #match broken! (or not found yet)
                matchpos = 0
                
                if curmatchlen >= record:
                    record = curmatchlen
                    recordstart = curmatchstart
        
        #check for possible RLE
        if curmatchlen + curmatchstart == curbyte and curmatchlen < 34:
            rlelen = 0
            for searchidx in range(curbyte, min(outsize, windowend)):
                if curmatchlen + rlelen == 34:
                    break
                elif data[searchidx] == data[(searchidx - curmatchstart) %% curmatchlen]:
                    rlelen += 1
                else:
                    break
            
            curmatchlen += rlelen
        
        #finally, determine what match to encode (or to just write a byte)
        if record > curmatchlen and record > 3:
            bundlecmds.append(1)
            operands_encoded.append((record, recordstart))
            
            curbyte += record
            windowstart += record
            windowend += record
            bytesleft -= record
        elif curmatchlen >= record and curmatchlen > 3:
            bundlecmds.append(1)
            operands_encoded.append((curmatchlen, curmatchstart))
            
            curbyte += curmatchlen
            windowstart += curmatchlen
            windowend += curmatchlen
            bytesleft -= curmatchlen
        else:
            bundlecmds.append(0)
            operands_encoded.append(data[curbyte])
            
            curbyte += 1
            windowstart += 1
            windowend += 1
            bytesleft -= 1
    
    #actually encode command bundles
    bundledat = 0
    bundleenc = []
    
    def range_forever(fromi,toi):
        while True:
            for i in range(fromi, toi):
                yield i
    
    curbyte = 0
    for cmd, operand, reset_if_15 in zip(bundlecmds, operands_encoded, range_forever(0,16)):
        bundledat << 1
        bundledat += cmd
        
        if cmd == 0:
            bundleenc.append(operand)
            curbyte += 1
        else:
            opdat = operand[0] - 3 << 11 + operand[1] & 0x7FF
            bundleenc.append(bytes(chr(opdat      & 0xFF), "raw_unicode_escape"))
            bundleenc.append(bytes(chr(opdat >> 8 & 0xFF), "raw_unicode_escape"))
        
        if reset_if_15 == 15:
            encoded.append(bytes(chr(bundledat      & 0xFF), "raw_unicode_escape"))
            encoded.append(bytes(chr(bundledat >> 8 & 0xFF), "raw_unicode_escape"))
            encoded.extend(bundleenc)
    
    return b"".join(bundleenc)
