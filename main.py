from tkinter import *
from tkinter import ttk
from PIL import Image, ImageTk

color0 = "#444466"
color1 = "#feffff"
color2 = "#6f9fbd"
color3 = "#38576b"
color4 = "#403d3d"
color5 = "#e06636"

window = Tk()
window.title("PokePython")
window.geometry("550x510")
window.configure(bg=color1)

ttk.Separator(window, orient=HORIZONTAL).grid(row=0, columnspan=1, ipadx=272)

style = ttk.Style(window)
style.theme_use("clam")

frame = Frame(window, width=550, height=290, relief="flat")
frame.grid(row=1, column=0)

pokeName = Label(frame, text='Pikachu', relief="flat", anchor=CENTER, font=("Fixedsys 20"), bg=color1, fg=color0)
pokeName.place(x=12, y=15)

pokeType = Label(frame, text='Elétrico', relief="flat", anchor=CENTER, font=("Ivy 10 bold"), bg=color1, fg=color0)
pokeType.place(x=12, y=50)

pokeId = Label(frame, text='#025', relief="flat", anchor=CENTER, font=("Ivy 10 bold"), bg=color1, fg=color0)
pokeId.place(x=12, y=75)

pikachuImg = Image.open('images/pikachu.png')
pikachuImg = pikachuImg.resize((238, 238))
pikachuIMG = ImageTk.PhotoImage(pikachuImg)

pokeImage = Label(frame, image=pikachuIMG, relief="flat", bg=color1, fg=color0)
pokeImage.place(x=12, y=75)
pokeId.lift()

pokeStats = Label(window, text='Status', relief="flat", anchor=CENTER, font=("Verdana 20"), bg=color1, fg=color0)
pokeStats.place(x=15, y=310)

pokeHP = Label(window, text='HP: 100', relief="flat", anchor=CENTER, font=("Verdana 10"), bg=color1, fg=color4)
pokeHP.place(x=15, y=350)

pokeAttack = Label(window, text='Ataque: 55', relief="flat", anchor=CENTER, font=("Verdana 10"), bg=color1, fg=color4)
pokeAttack.place(x=15, y=370)

pokeDefense = Label(window, text='Defesa: 40', relief="flat", anchor=CENTER, font=("Verdana 10"), bg=color1, fg=color4)
pokeDefense.place(x=15, y=390)

pokeSpeed = Label(window, text='Velocidade: 90', relief="flat", anchor=CENTER, font=("Verdana 10"), bg=color1, fg=color4)
pokeSpeed.place(x=15, y=410)

poketotal = Label(window, text='Total: 285', relief="flat", anchor=CENTER, font=("Verdana 10"), bg=color1, fg=color4)
poketotal.place(x=15, y=430)

window.mainloop()
