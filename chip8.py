import binascii
import numpy as np

import threading
import time

class Chip8:	
	def __init__(self):
		self.memory = [0x00]*0x1000
	
		self.V = [0x00]*16
		self.I = 0x00
		self.delay_timer = 0x00
		self.sound_timer = 0x00
		
		self.PC = 0x200
		self.SP = 0x00
	
		self.stack = [0x0000]*16
		
		self.display = np.zeros((64, 32))

		self.need_redraw = False
	
	def load_file(self, file):
		'''
		Loads the file and stores the program in the Chip8's memory
		starting from address 0x200
		'''
		# Opens the file and parses every byte into a list
		f = open(file, 'rb')
		string = str(binascii.hexlify(f.read()))[2:-1]
	
		split_string = lambda x, n: [x[i:i+n] for i in range(0, len(x), n)]
		string = split_string(string, 2)
		f.close()
		
		# Stores the program in the memory space starting from 0x200
		offset = 0x0
		for s in string:
			self.memory[0x200 + offset] = s.upper()
			offset += 0x1
			
	def load_character_set(self):
		'''
		Loads the character set into memory starting at location 0x000
		'''
		character_set = [
			0xF0, 0x90, 0x90, 0x90, 0xF0, #0
			0x20, 0x60, 0x20, 0x20, 0x70, #1
			0xF0, 0x10, 0xF0, 0x80, 0xF0, #2
			0xF0, 0x10, 0xF0, 0x10, 0xF0, #3
			0x90, 0x90, 0xF0, 0x10, 0x10, #4
			0xF0, 0x80, 0xF0, 0x10, 0xF0, #5
			0xF0, 0x80, 0xF0, 0x90, 0xF0, #6
			0xF0, 0x10, 0x20, 0x40, 0x40, #7
			0xF0, 0x90, 0xF0, 0x90, 0xF0, #8
			0xF0, 0x90, 0xF0, 0x10, 0xF0, #9
			0xF0, 0x90, 0xF0, 0x90, 0x90, #A
			0xE0, 0x90, 0xE0, 0x90, 0xE0, #B
			0xF0, 0x80, 0x80, 0x80, 0xF0, #C
			0xE0, 0x90, 0x90, 0x90, 0xE0, #D
			0xF0, 0x80, 0xF0, 0x80, 0xF0, #E
			0xF0, 0x80, 0xF0, 0x80, 0x80  #F
		]
		
		offset = 0x0
		for s in character_set:
			self.memory[0x0 + offset] = hex(s).upper()[2:]
			offset += 0x1
	
	def execute_opcode(self, op):
		# Precalculates the (possible) parameters for opcodes
		nnn = int(op[1] + op[2] + op[3], 16)
		nn = int(op[2] + op[3], 16)
		n = int(op[3], 16)
		
		x = int(op[1], 16)
		y = int(op[2], 16)
		
		# Increments by 2 regardless of instruction
		self.PC += 2
		
		if(op == '00E0'):
			'''
			00E0 - CLS
			Clear the display
			'''
			self.display = np.zeros((64, 32))
			self.need_redraw = True
		elif(op == '00EE'):
			'''
			00EE - RET
			Return from a subroutine
			'''
			self.PC = self.stack[self.SP-1]
			self.SP -= 1
			self.stack[self.SP] = 0x0		
		elif(op[0] == '1'):
			'''
			1nnn - JP address
			Jump to location nnn
			'''
			self.PC = nnn
		elif(op[0] == '2'):
			'''
			2nnn - CALL addr
			Call subroutine at nnn
			'''
			self.stack[self.SP] = self.PC
			self.SP += 1
			self.PC = nnn		
		elif(op[0] == '3'):
			'''
			3xkk - SE Vx, byte
			Skip next instruction if Vx == kk
			'''
			if(self.V[x] == nn):
				self.PC += 2	# Increments PC again if condition
		elif(op[0] == '4'):
			'''
			4xkk - SNE Vx, byte
			Skip next instruction if Vx != kk
			'''
			if(self.V[x] != nn):
				self.PC += 2	# Increments PC again if condition
		elif(op[0] == '5'):
			'''
			5xy0 - SE Vx, Vy
			Skip next instruction if Vx = Vy
			'''
			if(self.V[x] == self.V[y]):
				self.PC += 2	# Increments PC again if condition
		elif(op[0] == '6'):
			'''
			6xkk - LD Vx, byte
			Set Vx = kk
			'''
			self.V[x] = nn
		elif(op[0] == '7'):
			'''
			7xkk - ADD Vx, byte
			Set Vx = Vx + kk
			'''
			self.V[x] += nn
		elif(op[0] == '8'):
			if(op[3] == '0'):
				'''
				8xy0 - LD Vx, Vy
				Set Vx = Vy
				'''
				self.V[x] = self.V[y]
			elif(op[3] == '1'):
				'''
				8xy1 - OR Vx, Vy
				Set Vx = Vx OR Vy
				'''
				self.V[x] = self.V[x] | self.V[y]
			elif(op[3] == 2):
				'''
				8xy2 - AND Vx, Vy
				Set Vx = Vx AND Vy
				'''
				self.V[x] = self.V[x] & self.V[y]
			elif(op[3] == 3):
				'''
				8xy3 - XOR Vx, Vy
				Set Vx = Vx XOR Vy
				'''
				self.V[x] = self.V[x] ^ self.V[y]
			elif(op[3] == '4'):
				'''
				8xy4 - ADD Vx, Vy
				Set Vx = Vx + Vy, set Vf = carry
				'''
				self.V[x] += self.V[y]
				if(self.V[x] > 0xFF):
					self.V[x] = self.V[x] & 0xFF
					self.V[0xF] = 1
				else:
					self.V[0xF] = 0
			elif(op[3] == '5'):
				'''
				8xy5 - SUB Vx, Vy
				Set Vx = Vx - Vy, set Vf = NOT borrow
				'''
				if(self.V[x] > self.V[y]):
					self.V[0xF] = 1
				else:
					self.V[0xF] = 0
				self.V[x] -= self.V[y]
			elif(op[3] == '6'):
				'''
				8xy6 - SHR Vx {, Vy}
				Set Vx = Vy SHR 1
				'''
				self.V[0xF] = self.V[y] & 0x1
				self.V[x] = self.V[y] >> 1
			elif(op[3] == '7'):
				'''
				8xy7 - SUBN Vx, Vy
				Set Vx = Vy - Vx, set Vf = NOT borrow
				'''
				if(self.V[y] > self.V[x]):
					self.V[0xF] = 0x1
				else:
					self.V[0xF] = 0x0
				self.V[x] = self.V[y] - self.V[x]
			elif(op[3] == 'E'):
				'''
				8xye - SHL Vx {, Vy}
				Set Vx = Vy SHL 1
				'''
				self.V[0xF] = (self.V[y] & 0x80) >> 7
				self.V[x] = self.V[y] << 1
		elif(op[0] == '9'):
			'''
			9xy0 - SNE Vx, Vy
			Skip next instruction if Vx != Vy}
			'''
			if(self.V[x] != self.V[y]):
				self.PC += 2
		elif(op[0] == 'A'):
			'''
			Annn - LD I, addr
			Set I = nnn
			'''
			self.I = nnn
		elif(op[0] == 'B'):
			'''
			Bnnn - JP V0, addr
			Jump to location nnn + V0
			'''
			self.PC == nnn + self.V[0]
		elif(op[0] == 'C'):
			'''
			Cxkk - RND Vx, byte
			Set Vx = random byte AND kk
			'''
			self.V[x] = hex(np.random.randint(0, 255)) & kk
		elif(op[0] == 'D'):
			'''
			Dxyn - DRW Vx, Vy, nibble
			Display n-byte sprite starting at memory location I at (Vx, Vy), set Vf = collision
			'''
			self.need_redraw = True

	def update_timers(self):
	    '''
	    Updates the sound and delay timers at a rate of 60Hz
	    '''
	    while(True):
	        if(self.sound_timer > 0):
	            self.sound_timer -= 1
	        if(self.delay_timer > 0):
	            self.delay_timer -= 1
	        if(self.sound_timer < 0):
	            self.sound_timer = 0
	        if(self.delay_timer < 0):
	            self.delay_timer = 0
	        time.sleep(1/60)

	def run(self):
		'''
		Runs the emulator until the program is killed
		'''
		threading.Thread(target=self.update_timers).start()
		INS_PER_SECOND = 1000
		self.sound_timer = 0xff
		while(True):
			print(self.sound_timer)
			op = self.memory[self.PC] + self.memory[self.PC+1]
			self.execute_opcode(op)
			time.sleep(1/INS_PER_SECOND)
			if(self.need_redraw):
				self.need_redraw = False
			
if __name__ == "__main__":
	chip = Chip8()
	chip.load_file('c8games/PONG')

	chip.load_character_set()

	chip.run()
