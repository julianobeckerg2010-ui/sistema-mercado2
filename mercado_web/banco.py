import hashlib
import sqlite3
from datetime import datetime


class MercadoDB:
    def __init__(self, caminho_banco="mercado_web.db"):
        self.caminho_banco = caminho_banco
        self.con = sqlite3.connect(caminho_banco)
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
        self.criar_tabelas()
        self.popular_dados_iniciais()

    def criar_tabelas(self):
        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                usuario TEXT NOT NULL UNIQUE,
                senha TEXT NOT NULL,
                perfil TEXT NOT NULL
            )
            """
        )

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL NOT NULL,
                categoria TEXT NOT NULL,
                estoque INTEGER NOT NULL DEFAULT 0,
                descricao TEXT DEFAULT ''
            )
            """
        )

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
            """
        )

        self.cur.execute(
            """
            CREATE TABLE IF NOT EXISTS pedido_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                nome_produto TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            )
            """
        )
        self.con.commit()

    def hash_senha(self, senha):
        return hashlib.sha256(senha.encode()).hexdigest()

    def popular_dados_iniciais(self):
        usuarios_padrao = [
            ("Administrador", "dono", self.hash_senha("admin123"), "dono"),
            ("Funcionário", "funcionario", self.hash_senha("func123"), "funcionario"),
        ]

        for usuario in usuarios_padrao:
            self.cur.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario[1],))
            if not self.cur.fetchone():
                self.cur.execute(
                    "INSERT INTO usuarios (nome, usuario, senha, perfil) VALUES (?, ?, ?, ?)",
                    usuario,
                )

        self.cur.execute("SELECT COUNT(*) AS total FROM produtos")
        if self.cur.fetchone()["total"] == 0:
            produtos = [
                ("Arroz Premium 5kg", 29.90, "Alimentos", 18, "Pacote premium, ideal para o dia a dia."),
                ("Feijão Carioca 1kg", 8.90, "Alimentos", 26, "Grãos selecionados e alta qualidade."),
                ("Macarrão Espaguete", 5.49, "Alimentos", 34, "Massa tradicional para receitas rápidas."),
                ("Leite Integral 1L", 5.99, "Bebidas", 40, "Leite integral longa vida."),
                ("Refrigerante Cola 2L", 10.99, "Bebidas", 20, "Bebida gelada para toda a família."),
                ("Café Torrado 500g", 16.50, "Alimentos", 15, "Café encorpado e aromático."),
                ("Detergente Neutro", 2.79, "Limpeza", 50, "Limpeza eficiente com alto rendimento."),
                ("Sabão em Pó 1,6kg", 19.90, "Limpeza", 17, "Roupas limpas e perfumadas."),
                ("Papel Higiênico 12 rolos", 18.90, "Higiene", 22, "Folha dupla, macio e resistente."),
                ("Shampoo Hidratante", 15.90, "Higiene", 14, "Cuidado diário para os cabelos."),
            ]
            self.cur.executemany(
                "INSERT INTO produtos (nome, preco, categoria, estoque, descricao) VALUES (?, ?, ?, ?, ?)",
                produtos,
            )

        self.con.commit()

    def autenticar(self, usuario, senha):
        senha_hash = self.hash_senha(senha)
        self.cur.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND senha = ?",
            (usuario.strip(), senha_hash),
        )
        return self.cur.fetchone()

    def criar_cliente(self, nome, usuario, senha):
        try:
            self.cur.execute(
                "INSERT INTO usuarios (nome, usuario, senha, perfil) VALUES (?, ?, ?, ?)",
                (nome.strip(), usuario.strip(), self.hash_senha(senha), "cliente"),
            )
            self.con.commit()
            return True, "Conta criada com sucesso!"
        except sqlite3.IntegrityError:
            return False, "Esse nome de usuário já está em uso."

    def buscar_produtos(self, busca="", categoria="Todas"):
        sql = "SELECT * FROM produtos WHERE 1=1"
        params = []

        if busca.strip():
            sql += " AND lower(nome) LIKE ?"
            params.append(f"%{busca.lower().strip()}%")

        if categoria and categoria != "Todas":
            sql += " AND categoria = ?"
            params.append(categoria)

        sql += " ORDER BY nome"
        self.cur.execute(sql, tuple(params))
        return self.cur.fetchall()

    def categorias(self):
        self.cur.execute("SELECT DISTINCT categoria FROM produtos ORDER BY categoria")
        return [linha[0] for linha in self.cur.fetchall()]

    def buscar_produto_por_id(self, produto_id):
        self.cur.execute("SELECT * FROM produtos WHERE id = ?", (int(produto_id),))
        return self.cur.fetchone()

    def adicionar_produto(self, nome, preco, categoria, estoque, descricao):
        self.cur.execute(
            "INSERT INTO produtos (nome, preco, categoria, estoque, descricao) VALUES (?, ?, ?, ?, ?)",
            (nome.strip(), float(preco), categoria.strip(), int(estoque), descricao.strip()),
        )
        self.con.commit()

    def atualizar_produto(self, produto_id, nome, preco, categoria, estoque, descricao):
        self.cur.execute(
            """
            UPDATE produtos
            SET nome = ?, preco = ?, categoria = ?, estoque = ?, descricao = ?
            WHERE id = ?
            """,
            (nome.strip(), float(preco), categoria.strip(), int(estoque), descricao.strip(), int(produto_id)),
        )
        self.con.commit()

    def remover_produto(self, produto_id):
        self.cur.execute("DELETE FROM produtos WHERE id = ?", (int(produto_id),))
        self.con.commit()

    def resumo_admin(self):
        self.cur.execute("SELECT COUNT(*) AS total FROM produtos")
        total_produtos = self.cur.fetchone()["total"]

        self.cur.execute("SELECT COALESCE(SUM(estoque), 0) AS total FROM produtos")
        total_estoque = self.cur.fetchone()["total"]

        self.cur.execute("SELECT COUNT(*) AS total FROM pedidos")
        total_pedidos = self.cur.fetchone()["total"]

        self.cur.execute("SELECT COALESCE(SUM(total), 0) AS total FROM pedidos")
        faturamento = self.cur.fetchone()["total"]

        return {
            "produtos": total_produtos,
            "estoque": total_estoque,
            "pedidos": total_pedidos,
            "faturamento": faturamento,
        }

    def criar_pedido(self, usuario_id, itens):
        if not itens:
            return False, "Carrinho vazio."

        total = 0
        produtos_atualizados = []

        for produto_id, item in itens.items():
            self.cur.execute("SELECT * FROM produtos WHERE id = ?", (int(produto_id),))
            produto = self.cur.fetchone()

            if not produto:
                return False, f"Produto ID {produto_id} não encontrado."

            if int(item["quantidade"]) > produto["estoque"]:
                return False, f"Estoque insuficiente para {produto['nome']}."

            subtotal = int(item["quantidade"]) * produto["preco"]
            total += subtotal
            produtos_atualizados.append((produto, int(item["quantidade"]), subtotal))

        criado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cur.execute(
            "INSERT INTO pedidos (usuario_id, total, status, criado_em) VALUES (?, ?, ?, ?)",
            (int(usuario_id), total, "Pago", criado_em),
        )
        pedido_id = self.cur.lastrowid

        for produto, quantidade, subtotal in produtos_atualizados:
            self.cur.execute(
                """
                INSERT INTO pedido_itens (pedido_id, produto_id, nome_produto, quantidade, preco_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (pedido_id, produto["id"], produto["nome"], quantidade, produto["preco"], subtotal),
            )
            self.cur.execute(
                "UPDATE produtos SET estoque = estoque - ? WHERE id = ?",
                (quantidade, produto["id"]),
            )

        self.con.commit()
        return True, f"Pedido #{pedido_id} finalizado com sucesso!"

    def pedidos_cliente(self, usuario_id):
        self.cur.execute(
            "SELECT * FROM pedidos WHERE usuario_id = ? ORDER BY id DESC",
            (int(usuario_id),),
        )
        return self.cur.fetchall()

    def pedidos_gerais(self):
        self.cur.execute(
            """
            SELECT pedidos.id, usuarios.nome, usuarios.usuario, pedidos.total, pedidos.status, pedidos.criado_em
            FROM pedidos
            INNER JOIN usuarios ON usuarios.id = pedidos.usuario_id
            ORDER BY pedidos.id DESC
            """
        )
        return self.cur.fetchall()

    def itens_pedido(self, pedido_id):
        self.cur.execute(
            "SELECT * FROM pedido_itens WHERE pedido_id = ? ORDER BY id",
            (int(pedido_id),),
        )
        return self.cur.fetchall()

    def fechar(self):
        self.con.close()
