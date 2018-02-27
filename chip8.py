import binascii
import numpy as np

import threading
import time

import pygame
import sys

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
		
		self.display = np.zeros(64 * 32, dtype=int)

		self.need_redraw = False

		# Maps Chip8 keys to a modern keyboard
		self.key_dict = {
			'0' : pygame.K_x,
			'1' : pygame.K_1,
			'2' : pygame.K_2,
			'3' : pygame.K_3,
			'4' : pygame.K_q,
			'5' : pygame.K_w,
			'6' : pygame.K_e,
			'7' : pygame.K_a,
			'8' : pygame.K_s,
			'9' : pygame.K_d,
			'A' : pygame.K_z,
			'B' : pygame.K_c,
			'C' : pygame.K_4,
			'D' : pygame.K_r,
			'E' : pygame.K_f,
			'F' : pygame.K_v
		}

		# Needed for inverse key lookups
		self.inv_key_dict = {v: k for k, v in self.key_dict.items()}
	
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
			self.display = np.zeros(64 * 32, dtype=int)
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
			self.V[x] &= 0xFF
		elif(op[0] == '8'):
			if(op[3] == '0'):
				'''
				8xy0 - LD Vx, Vy
				Set Vx = Vy
				'''
				self.V[x] = self.V[y]
				self.V[x] &= 0xFF
			elif(op[3] == '1'):
				'''
				8xy1 - OR Vx, Vy
				Set Vx = Vx OR Vy
				'''
				self.V[x] |= self.V[y]
				self.V[x] &= 0xFF
			elif(op[3] == 2):
				'''
				8xy2 - AND Vx, Vy
				Set Vx = Vx AND Vy
				'''
				self.V[x] &= self.V[y]
				self.V[x] &= 0xFF
			elif(op[3] == 3):
				'''
				8xy3 - XOR Vx, Vy
				Set Vx = Vx XOR Vy
				'''
				self.V[x] ^= self.V[y]
				self.V[x] &= 0xFF
			elif(op[3] == '4'):
				'''
				8xy4 - ADD Vx, Vy
				Set Vx = Vx + Vy, set Vf = carry
				'''
				res = int(self.V[x]) + int(self.V[y])
				self.V[x] = res
				if res > 255:
					self.V[0xF] = 0x1
				else:
					self.V[0xF] = 0x0
				self.V[x] &= 0xFF
			elif(op[3] == '5'):
				'''
				8xy5 - SUB Vx, Vy
				Set Vx = Vx - Vy, set Vf = NOT borrow
				'''
				res = int(self.V[x]) - int(self.V[y])
				self.V[x] = res
				if res < 0:
					self.V[0xF] = 0x0
				else:
					self.V[0xF] = 0x1
				self.V[x] &= 0xFF
			elif(op[3] == '6'):
				'''
				8xy6 - SHR Vx {, Vy}
				Set Vx = Vy SHR 1
				'''
				self.V[0xF] = self.V[y] & 0b00000001
				self.V[x] = self.V[y] >> 1
				self.V[x] &= 0xFF
			elif(op[3] == '7'):
				'''
				8xy7 - SUBN Vx, Vy
				Set Vx = Vy - Vx, set Vf = NOT borrow
				'''
				res = int(self.V[y]) - int(self.V[x])
				self.V[x] = res
				if res < 0:
					self.V[0xF] = 0x0
				else:
					self.V[0xF] = 0x1
				self.V[x] &= 0xFF
			elif(op[3] == 'E'):
				'''
				8xye - SHL Vx {, Vy}
				Set Vx = Vy SHL 1
				'''
				self.V[0xF] = (self.V[y] & 0b10000000) >> 7
				self.V[x] = self.V[y] << 1
				self.V[x] &= 0xFF
		elif(op[0] == '9'):
			'''
			9xy0 - SNE Vx, Vy
			Skip next instruction if Vx != Vy
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
			self.V[x] = (np.random.randint(0, 255) & nn) & 0xFF
		elif(op[0] == 'D'):
			'''
			Dxyn - DRW Vx, Vy, nibble
			Display n-byte sprite starting at memory location I at (Vx, Vy), set Vf = collision
			'''

			self.V[0xF] = 0x0

			for row in range(n):
				for col in range(8):
					pixel = int(self.memory[self.I + row], 16)

					if(pixel & (0x80 >> col) != 0):
						pos_x = (self.V[x]+col) % 64
						pos_y = (self.V[y]+row) % 32

						if(self.display[64*pos_y + pos_x] == 1):
							self.display[64*pos_y + pos_x] = 0
							self.V[0xF] = 1
						else:
							self.display[64 * pos_y + pos_x] = 1

			self.need_redraw = True
		elif(op[0] == 'E'):
			if(op[2] + op[3] == '9E'):
				'''
				Ex9E - SKP Vx
				Skip next instruction if key with the value of Vx is pressed
				'''
				val = hex(self.V[x])[2]
				keys_pressed = pygame.key.get_pressed()

				if(keys_pressed[self.key_dict[val.upper()]]):
					self.PC += 2
			elif(op[2] + op[3] == 'A1'):
				'''
				ExA1 - SKNP Vx
				Skip next instruction if key with the value of Vx is not pressed
				'''
				val = hex(self.V[x])[2]
				keys_pressed = pygame.key.get_pressed()

				if(not keys_pressed[self.key_dict[val.upper()]]):
					self.PC += 2
		elif(op[0] == 'F'):
			if(op[2] + op[3] == '07'):
				'''
				Fx07 - LD Vx, DT
				The value of DT is placed into Vx
				'''
				self.V[x] = self.delay_timer
				self.V[x] &= 0xFF
			elif(op[2] + op[3] == '0A'):
				'''
				Fx0A - LD Vx, K
				Wait for a key press, store the value of the key in Vx
				'''
				got_press = False
				while not got_press:
					for event in pygame.event.get():
						if(event.type == pygame.QUIT):
								pygame.display.quit()
								pygame.quit()
								sys.exit()
						if event.type == pygame.KEYDOWN:
							pressed_keys = pygame.key.get_pressed()
							valid_keys = list(self.inv_key_dict.keys())
							for k in valid_keys:
								if(pressed_keys[k]):
									self.V[x] = int(hex(self.inv_key_dict[k]))
									got_press = True
			elif(op[2] + op[3] == '15'):
				'''
				Fx15 - LD DT, Vx
				Set delay timer = Vx
				'''
				self.delay_timer = self.V[x]
			elif(op[2] + op[3] == '18'):
				'''
				Fx18 - LD ST, Vx
				Set sound timer = Vx
				'''
				self.sound_timer = self.V[x]
			elif(op[2] + op[3] == '1E'):
				'''
				Fx1E - Add I, Vx
				Set I = I + Vx
				'''
				self.I += self.V[x]
			elif(op[2] + op[3] == '29'):
				'''
				Fx29 - LD F, Vx
				Set I = location of sprite for digit Vx
				'''
				self.I = 0x5 * self.V[x]
			elif(op[2] + op[3] == '33'):
				'''
				Fx33 - LD B, Vx
				Store BCD representation of Vx in memory locations I, I+1, I+2
				'''
				bcd = int(self.V[x])
				h = int(bcd / 100)
				t = int((bcd % 100) / 10)
				d = int((bcd % 100) % 10)

				self.memory[self.I] = h
				self.memory[self.I+1] = t
				self.memory[self.I+2]= d
			elif(op[2] + op[3] == '55'):
				'''
				Fx55 - LD [I], Vx
				Store registers V0 through Vx in memory starting at location I
				'''
				for k in range(x+1):
					self.memory[self.I+k] = self.V[k]
			elif(op[2] + op[3] == '65'):
				'''
				Fx65 - LD Vx, [I]
				Read registers V0 through Vx from memory starting at location I
				'''
				for k in range(x+1):
					self.V[k] = self.memory[self.I+k]

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

	def draw_from_array(self, screen, array, PIXEL_WIDTH, PIXEL_HEIGHT):
		'''
		Takes in data from array representing pixels on the screen
		and draws the corresponding rectangles with pygame
		'''
		screen_width = screen.get_rect()[2]
		screen_height = screen.get_rect()[3]

		for s in range(len(array)):
			if(array[s] != 0):
				pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(s*(screen_width/PIXEL_WIDTH) % screen_width, int(s*(screen_width/PIXEL_WIDTH) / screen_width)*(screen_width/PIXEL_WIDTH), screen_width/PIXEL_WIDTH, screen_height/PIXEL_HEIGHT))


	def run(self):
		'''
		Runs the emulator until the program is killed
		'''
		screen = pygame.display.set_mode((640, 320))
		pygame.display.set_caption('Chip 8 Interpreter')

		threading.Thread(target=self.update_timers).start()
		INS_PER_SECOND = 50000
		done = False

		while not done:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					done = True

			op = self.memory[self.PC] + self.memory[self.PC+1]
			self.execute_opcode(op)

			if(self.need_redraw):
				screen.fill((0, 0, 0))
				self.draw_from_array(screen, self.display, 64, 32)
				pygame.display.flip()
				self.need_redraw = False

			time.sleep(1/INS_PER_SECOND)
			
if __name__ == "__main__":
	pygame.init()

	chip = Chip8()
	chip.load_file('c8games/HIDDEN')

	chip.load_character_set()

	chip.run()

	pygame.display.quit()
	pygame.quit()
	sys.exit()