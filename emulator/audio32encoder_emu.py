from qiling import Qiling
from qiling.const import QL_VERBOSE
from qiling.const import QL_ARCH, QL_ENDIAN, QL_OS, QL_INTERCEPT, QL_CALL_BLOCK
from qiling.os.const import STRING, DWORD
from keystone import *
import struct

class Audio32Encoder:
    def __init__(self):
        # libAudio32Encoder.so from CloudPets app com.spiraltoys.cloudpets2.free
        # md5sum: a7423f06f95e270c86cb89dcf8d57ed8
        argv = [r'apk2/lib/armeabi-v7a/libAudio32Encoder.so']

        # instantiate a Qiling object using above arguments and set emulation verbosity level to DEBUG.
        # additional settings are read from profile file
        self.ql = Qiling(argv, './', verbose=QL_VERBOSE.DEBUG, thumb=True, profile="test_os.ql")

        # ql.debugger = "qdb"

        # map input buffer
        self.input_addr = 0x10000000
        self.ql.mem.map(self.input_addr, 4096, info="[input buffer]")

        def asm2byte(asm):
            ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
            (t, _) = ks.asm(asm)
            return bytes(t)

        self.trap_address = 0xdead0000
        trap_code = asm2byte("b .")
        self.ql.mem.map(self.trap_address, 4096, info="[exit trap]")
        self.ql.mem.write(self.trap_address, trap_code * (4096 // len(trap_code)))

        def my_pow(ql: Qiling):
            params = ql.os.resolve_fcall_params({'a0': DWORD, 'a1': DWORD, 'b0': DWORD, 'b1': DWORD})
            x = struct.pack("<II", params['a0'], params['a1'])
            a = struct.unpack("<d", x)[0]
            x = struct.pack("<II", params['b0'], params['b1'])
            b = struct.unpack("<d", x)[0]

            val = a ** b
            x = struct.unpack("<II", struct.pack("<d", val))

            ql.arch.regs.r0 = x[0]
            ql.arch.regs.r1 = x[1]

            return QL_CALL_BLOCK

        self.ql.os.set_api("pow", my_pow, QL_INTERCEPT.CALL)

    def audio_encode_init(self, samples_rate):
        audio_encode_init_fn = 0x3108
        self.ql.log.debug(f'call audio_encode_init(samples_rate = {samples_rate})')
        self.ql.arch.regs.r0 = samples_rate # sampling rate
        self.ql.arch.regs.lr = self.trap_address # set to infinite trap
        self.ql.run(begin=audio_encode_init_fn, end=self.trap_address)

    def get_number_of_16bit_words_per_frame(self):
        #read gl_number_of_16bit_words_per_frame
        words_per_frame = struct.unpack("<H", self.ql.mem.read(0x1b928, 2))[0]
        self.ql.log.debug(f'gl_number_of_16bit_words_per_frame = {words_per_frame}')
        return words_per_frame

    def audio_encode(self, input_data):
        audio_encode_fn = 0x3530
        self.ql.mem.write(self.input_addr, bytes(input_data))
        self.ql.arch.regs.r0 = self.input_addr # input samples
        self.ql.arch.regs.lr = self.trap_address # set to infinite trap
        self.ql.run(begin=audio_encode_fn, end=self.trap_address)
    
    def endianessT(self, val) -> int:
        endianessT_fn = 0x41b8
        self.ql.arch.regs.r0 = val # input value
        self.ql.arch.regs.lr = self.trap_address # set to infinite trap
        self.ql.run(begin=endianessT_fn, end=self.trap_address)

        out = self.ql.arch.regs.r0
        self.ql.log.debug(f'endianessT(0x{val:04x}) = 0x{out:04x}')

        return out

    def get_gl_history(self) -> bytes:
        gl_history_addr = 0x1b9bc
        return self.ql.mem.read(gl_history_addr, 640)

    def get_gl_frame_cnt(self) -> int:
        gl_frame_cnt_addr = 0xeae4
        x = self.ql.mem.read(gl_frame_cnt_addr, 4)
        return struct.unpack('<I', x)[0]

    def get_gl_out_words(self, count) -> bytes:
        gl_out_words_addr = 0x1b92c
        x = self.ql.mem.read(gl_out_words_addr, count * 2)
        return x

    def get_gl_mag_shift(self) -> int:
        gl_mag_shift_addr = 0x1af1c
        x = self.ql.mem.read(gl_mag_shift_addr, 4)
        return struct.unpack('<i', x)[0]

    def get_gl_mlt_coefs(self) -> bytes:
        gl_mlt_coefs_addr = 0x1af24
        x = self.ql.mem.read(gl_mlt_coefs_addr, 640)
        return x

if __name__ == "__main__":
    import wave
    import array
    import sys
    from binascii import unhexlify, hexlify

    enc = Audio32Encoder()
    enc.endianessT(0x1)

    CHUNK_SIZE = 320

    def open_wav(filename: str) -> wave.Wave_read:
        wav = wave.open(filename, 'rb')
        wav_params = wav.getparams()
        assert wav_params.framerate == 16000
        assert wav_params.sampwidth == 2
        assert wav_params.nchannels == 1
        return wav
    
    def iter_wav_data(wav: wave.Wave_read, chunk_size: int, min_padding=0):
        wav.rewind()
        nchunks = wav.getnframes() // chunk_size
        for n in range(0, nchunks):
            d = wav.readframes(chunk_size)
            if len(d) < chunk_size:
                d += b'\0\0' * (chunk_size - len(d))
            a =  array.array('h')
            a.frombytes(d)
            yield a
        if min_padding:
            a =  array.array('h')
            a.frombytes(b'\0\0'*min_padding)
            yield a

    def get_file_header(sample_rate: int, frames: int, words_per_frame: int):
        a = array.array('H')
        a.append(0x5541) # 'AU'
        a.append(sample_rate)
        a.append(1600)
        a.append(1)
        a.append(frames)
        a.append(0)
        a.append(frames * words_per_frame)
        return a.tobytes() + unhexlify('0000000000000000000000001000ffffffff')

    def encode_audio(wav: wave.Wave_read) -> bytes:
        
        print('audio_encode_init {} {}'.format(wav.getframerate(), wav.getframerate() // 50))
        enc.audio_encode_init(wav.getframerate())
        
        words_per_frame = enc.get_number_of_16bit_words_per_frame()
        in_data = bytearray(CHUNK_SIZE*2)
        out_data = bytearray()
        nn = 0

        for n, c in enumerate(iter_wav_data(wav, CHUNK_SIZE, CHUNK_SIZE)):
            for i, s in enumerate(c):
                in_data[i*2] = s & 0xff
                in_data[i*2+1] = (s >> 8) & 0xff
            gl_history = enc.get_gl_history()
            if n == 0:
                print('gl_history={}'.format(hexlify(gl_history)))
            result = enc.audio_encode(in_data)  
            gl_out_words = enc.get_gl_out_words(words_per_frame)
            gl_mlt_coefs = enc.get_gl_mlt_coefs()
            gl_history = enc.get_gl_history()
            gl_mag_shift = enc.get_gl_mag_shift()
            print('gl_mag_shift={}'.format(gl_mag_shift))
            if nn < 2:
                print('gl_mlt_coefs={}'.format(hexlify(gl_mlt_coefs)))
                print('gl_history={}'.format(hexlify(gl_history)))
                print("in_data: len={} {}".format(len(in_data), hexlify(in_data)))
                print("out_data: len={} {}".format(len(gl_out_words), hexlify(gl_out_words)))
            out_data.extend(gl_out_words[:])
            nn += 1
        print('nn: {}'.format(nn))
        nframes = enc.get_gl_frame_cnt()
        
        print('nframes: {} words_per_frame: {}'.format(nframes, words_per_frame))
        header = get_file_header(sample_rate=wav.getframerate(), frames = nframes, words_per_frame = words_per_frame)
        print('out_data len: {}'.format(len(out_data)))
        return header + out_data

    if len(sys.argv) < 3:
        print('Usage: {} infile outfile'.format(sys.argv[0]))
        exit()
    infile = sys.argv[1]
    outfile = sys.argv[2]

    wav = open_wav(infile)
    data = encode_audio(wav)
    with open(outfile, 'wb') as f:
        f.write(data)