import os,re,shutil,tempfile,fitz,pypdf
import tkinter as tk
from tkinter import filedialog,messagebox,simpledialog
import customtkinter as ctk
from PIL import Image,ImageTk
from tkinterdnd2 import DND_FILES,TkinterDnD

ctk.set_appearance_mode("System")

class PDFEditorApp(ctk.CTk,TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion=TkinterDnD._require(self)
        self.title("PDFEditorApp - shuffle & annotation")
        self.geometry("750x600");self.minsize(650,450)
        self.pages=[];self.ann_mode=None
        self._build_ui()
        self.drop_target_register(DND_FILES);self.dnd_bind("<<Drop>>",self._on_drop)

    def _build_ui(self):
        top=ctk.CTkFrame(self,height=60);top.pack(fill="x",padx=20,pady=(20,10))
        ctk.CTkButton(top,text="open pdf",command=self.open_pdf).pack(side="left",padx=10,pady=10)
        self.file_label=ctk.CTkLabel(top,text="ファイルを選択するか、下にドロップしてください",text_color="gray");self.file_label.pack(side="left",padx=10,pady=10)
        self.list_frame=ctk.CTkScrollableFrame(self,label_text="Contents List (PDFをDrag&Drop)");self.list_frame.pack(fill="both",expand=True,padx=20,pady=10)
        self.list_frame.drop_target_register(DND_FILES);self.list_frame.dnd_bind("<<Drop>>",self._on_drop)
        bottom=ctk.CTkFrame(self,height=60);bottom.pack(fill="x",padx=20,pady=(10,20))
        self.save_btn=ctk.CTkButton(bottom,text="この並び順で名前を付けて保存",command=self.save_pdf,state="disabled");self.save_btn.pack(side="right",padx=10,pady=10)

    def open_pdf(self):
        p=filedialog.askopenfilename(title="ファイルを選択",filetypes=[("pdfs","*.pdf")])
        if p:self.pages.clear();self._add_pdf(p)

    def _parse_dnd(self,s):
        if not isinstance(s,str):return[]
        return [m[0] or m[1] for m in re.findall(r'\{([^}]*)\}|([^ ]+)',s) if (m[0] or m[1])]

    def _on_drop(self,event):
        try:
            files=self._parse_dnd(event.data);ok=False
            for f in files:
                f=f.strip()
                if f.lower().endswith('.pdf') and os.path.exists(f):self._add_pdf(f);ok=True
            if not ok:messagebox.showwarning("警告","有効なPDFファイルが検出されませんでした")
        except Exception as e:messagebox.showerror("ドロップエラー",f"ドロップ処理中に例外が発生しました:\n{e}")

    def _thumb(self,f,p,zoom=0.15):
        doc=fitz.open(f);pg=doc.load_page(p);pix=pg.get_pixmap(matrix=fitz.Matrix(zoom,zoom))
        img=Image.frombytes("RGB",[pix.width,pix.height],pix.samples);doc.close();return img

    def _add_pdf(self,fpath):
        try:
            rdr=pypdf.PdfReader(fpath);name=os.path.basename(fpath);n=len(rdr.pages)
            for i in range(n):
                pil=self._thumb(fpath,i);cim=ctk.CTkImage(light_image=pil,dark_image=pil,size=pil.size)
                self.pages.append({"file":fpath,"page":i,"label":f"{name} - {i+1}ページ目","thumb":cim})
            self._update_ui();self._refresh_list()
        except Exception as e:messagebox.showerror("エラー",f"PDFの処理に失敗しました:\n{e}")

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():w.destroy()
        for idx,pi in enumerate(self.pages):
            row=ctk.CTkFrame(self.list_frame);row.pack(fill="x",padx=5,pady=4)
            lbl_img=ctk.CTkLabel(row,text="",image=pi['thumb']);lbl_img.pack(side="left",padx=10,pady=2);lbl_img.bind("<Double-1>",lambda e,p=pi:self._open_zoom(p))
            l=ctk.CTkLabel(row,text=pi['label'],anchor='w');l.pack(side='left',padx=10,fill='x',expand=True);l.bind("<Double-1>",lambda e,p=pi:self._open_zoom(p))
            ctk.CTkButton(row,text="削除",width=65,fg_color="#A34949",hover_color="#BD5A5A",command=lambda i=idx:self._del(i)).pack(side='right',padx=10)
            if idx<len(self.pages)-1:ctk.CTkButton(row,text="↓ 下へ",width=60,command=lambda i=idx:self._move(i,1)).pack(side='right',padx=2)
            else:ctk.CTkLabel(row,text="",width=60).pack(side='right',padx=2)
            if idx>0:ctk.CTkButton(row,text="↑ 上へ",width=60,command=lambda i=idx:self._move(i,-1)).pack(side='right',padx=2)
            else:ctk.CTkLabel(row,text="",width=60).pack(side='right',padx=2)

    def _open_zoom(self,page_info):
        z=ctk.CTkToplevel(self);z.title(f"拡大プレビュー - {page_info['label']}");z.attributes("-topmost",True)
        zoom=0.9;pil=self._get_large(page_info['file'],page_info['page'],zoom)
        tb=ctk.CTkFrame(z);tb.pack(fill='x',padx=8,pady=(8,0))
        tbtn=ctk.CTkButton(tb,text="テキスト注釈",command=lambda:self._toggle_ann('text',tbtn));tbtn.pack(side='left',padx=6)
        ct=ctk.CTkButton(tb,text="注釈一覧",command=lambda p=page_info:self._show_ann(p));ct.pack(side='left',padx=6)
        ctk.CTkButton(tb,text="閉じる",command=z.destroy).pack(side='right',padx=6)
        frm=tk.Frame(z);frm.pack(fill='both',expand=True,padx=10,pady=10)
        canvas=tk.Canvas(frm,width=pil.width,height=pil.height);canvas.pack(fill='both',expand=True)
        tkimg=ImageTk.PhotoImage(pil);canvas.image=tkimg;canvas.create_image(0,0,anchor='nw',image=tkimg)
        def on_click(e):
            if self.ann_mode=='text':
                txt=simpledialog.askstring('注釈テキスト','注釈内容を入力してください:')
                if txt:
                    x=e.x/zoom;y=e.y/zoom;self._add_text_ann(page_info,x,y,txt);self._refresh_list()
        canvas.bind('<Button-1>',on_click)
        z.geometry(f"{pil.width+50}x{min(pil.height+70,900)}")

    def _get_large(self,f,p,zoom):
        doc=fitz.open(f);pg=doc.load_page(p);pix=pg.get_pixmap(matrix=fitz.Matrix(zoom,zoom));img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);doc.close();return img

    def _add_text_ann(self,page_info,x,y,text):
        f=page_info['file'];p=page_info['page']
        try:
            doc=fitz.open(f);pg=doc.load_page(p);rect=fitz.Rect(x,y,x+200,y+50)
            pg.add_freetext_annot(rect,text,fontsize=14,fontname='cjk',text_color=(0,0,0))
            fd,tmp=tempfile.mkstemp(suffix='.pdf');os.close(fd);doc.save(tmp);doc.close();shutil.move(tmp,f)
            self._update_thumb(f,p);messagebox.showinfo('注釈追加','注釈を追加しました。')
        except Exception as e:messagebox.showerror('注釈エラー',f'注釈の追加に失敗しました:\n{e}')

    def _show_ann(self,page_info):
        f=page_info['file'];p=page_info['page']
        try:
            doc=fitz.open(f);pg=doc.load_page(p);anns=list(pg.annots() or [])
            if not anns:doc.close();messagebox.showinfo('注釈一覧','このページに注釈はありません。');return
            w=ctk.CTkToplevel(self);w.title(f"注釈一覧 - {page_info['label']}");w.geometry('400x300')
            cont=ctk.CTkScrollableFrame(w);cont.pack(fill='both',expand=True,padx=8,pady=8)
            for a in anns:
                info=a.info or {};content=info.get('content') or info.get('title') or str(info)
                fr=ctk.CTkFrame(cont);fr.pack(fill='x',padx=6,pady=6);ctk.CTkLabel(fr,text=content,anchor='w').pack(side='left',fill='x',expand=True,padx=(6,8))
                def _del(a=a):
                    try:
                        pg.delete_annot(a);fd,tmp=tempfile.mkstemp(suffix='.pdf');os.close(fd);doc.save(tmp);doc.close();shutil.move(tmp,f);messagebox.showinfo('削除','注釈を削除しました。');w.destroy();self._update_thumb(f,p)
                    except Exception as e:messagebox.showerror('削除エラー',f'注釈の削除に失敗しました:\n{e}')
                ctk.CTkButton(fr,text='削除',width=80,command=_del).pack(side='right',padx=6)
        except Exception as e:messagebox.showerror('注釈一覧エラー',f'注釈一覧を取得できませんでした:\n{e}')

    def _update_thumb(self,f,p):
        try:
            pil=self._thumb(f,p);cim=ctk.CTkImage(light_image=pil,dark_image=pil,size=pil.size)
            for e in self.pages:
                if e['file']==f and e['page']==p:e['thumb']=cim
            self._update_ui()
        except Exception:pass

    def _move(self,i,d):
        j=i+d
        if 0<=j<len(self.pages):self.pages[i],self.pages[j]=self.pages[j],self.pages[i];self._refresh_list()

    def save_pdf(self):
        if not self.pages:return
        sp=filedialog.asksaveasfilename(title='別名で保存',defaultextension='.pdf',filetypes=[('PDF files','*.pdf')])
        if not sp:return
        try:
            nd=fitz.open()
            for pi in self.pages:
                src=fitz.open(pi['file']);nd.insert_pdf(src,from_page=pi['page'],to_page=pi['page']);src.close()
            nd.save(sp);nd.close();messagebox.showinfo('成功','PDFが正しく結合・保存されました！')
        except Exception as e:messagebox.showerror('エラー',f'ファイルの保存中にエラーが発生しました:\n{e}')

    def _update_ui(self):
        if self.pages:
            self.file_label.configure(text=f"現在の総ページ数: {len(self.pages)} ページ",text_color='green');self.save_btn.configure(state='normal')
        else:
            self.file_label.configure(text='ファイルを選択するか、下にドロップしてください',text_color='gray');self.save_btn.configure(state='disabled')

    def _del(self,i):
        if 0<=i<len(self.pages):self.pages.pop(i);self._update_ui();self._refresh_list()

    def _toggle_ann(self,mode,btn):
        self.ann_mode=None if self.ann_mode==mode else mode
        try:btn.configure(fg_color=("#318216" if self.ann_mode==mode else None))
        except Exception:pass

if __name__=="__main__":PDFEditorApp().mainloop()
