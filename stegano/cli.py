#!/usr/bin/env python3
import os, sys, time, subprocess, shutil
from pathlib import Path
from .core import hide, extract, inspect, remove

def clear():
    os.system("clear")

def intro():
    clear()
    print("\n\n")
    print("                         STEGANO TOOL")
    print("                          by Aether OS")
    time.sleep(0.7)

def menu():
    items=["Hide File","Extract File","View Embedded Data","Remove Embedded Data","Start Web UI","Settings","Exit"]
    idx=0
    while True:
        clear()
        print("\n  STEGANO TOOL\n  by Aether OS\n")
        for i,x in enumerate(items):
            print(("  \033[97m❯ "+x+"\033[0m") if i==idx else "    "+x)
        print("\n  ↑/↓ Navigate   Enter Select")
        c=sys.stdin.read(1)
        if c=="\x1b":
            seq=sys.stdin.read(2)
            if seq=="[A": idx=(idx-1)%len(items)
            elif seq=="[B": idx=(idx+1)%len(items)
        elif c in ("\n","\r"):
            return idx

def ask(prompt):
    return input(prompt).strip()

def main():
    intro()
    while True:
        choice=menu()
        if choice==0:
            img=ask("\nPNG image path: ")
            payload=ask("File to embed: ")
            pw=ask("Password (leave blank for none): ")
            out=ask("Output PNG (blank = automatic): ") or None
            try:
                p,meta=hide(img,payload,out,pw or None)
                print(f"\nCreated: {p}\nEmbedded: {meta['name']} ({meta['size']} bytes)")
            except Exception as e: print(f"\nError: {e}")
            input("\nPress Enter...")
        elif choice==1:
            img=ask("\nStegano PNG path: "); out=ask("Output directory (blank = image folder): ") or None
            pw=ask("Password if protected: ")
            try: print(f"\nExtracted: {extract(img,out,pw or None)}")
            except Exception as e: print(f"\nError: {e}")
            input("\nPress Enter...")
        elif choice==2:
            img=ask("\nStegano PNG path: ")
            try:
                for k,v in inspect(img).items(): print(f"{k}: {v}")
            except Exception as e: print(f"\nError: {e}")
            input("\nPress Enter...")
        elif choice==3:
            img=ask("\nStegano PNG path: "); out=ask("Clean output PNG (blank = automatic): ") or None
            try: print(f"\nCreated: {remove(img,out)}")
            except Exception as e: print(f"\nError: {e}")
            input("\nPress Enter...")
        elif choice==4:
            from .web import serve
            serve()
            input("\nWeb server stopped. Press Enter...")
        elif choice==5:
            print("\nSettings are kept minimal for the offline-first build.")
            input("\nPress Enter...")
        else:
            clear(); print("\nGoodbye.\n"); return

if __name__=="__main__":
    main()
