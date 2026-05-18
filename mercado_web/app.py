from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from banco import MercadoDB


app = Flask(__name__)
app.config["SECRET_KEY"] = "troque-esta-chave-por-uma-chave-segura"
app.config["DB_PATH"] = "mercado_web.db"



def get_db():
    if "db" not in g:
        g.db = MercadoDB(app.config["DB_PATH"])
    return g.db


@app.teardown_appcontext
def fechar_conexao(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.fechar()


with app.app_context():
    get_db()


@app.context_processor
def inject_globals():
    carrinho = session.get("carrinho", {})
    total_itens = sum(int(item["quantidade"]) for item in carrinho.values())
    total_valor = sum(float(item["subtotal"]) for item in carrinho.values())
    return {
        "usuario_logado": session.get("usuario"),
        "carrinho_total_itens": total_itens,
        "carrinho_total_valor": total_valor,
    }



def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "usuario" not in session:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped_view



def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        usuario = session.get("usuario")
        if not usuario:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("index"))
        if usuario["perfil"] not in ["dono", "funcionario"]:
            flash("Acesso permitido apenas para a equipe administrativa.", "danger")
            return redirect(url_for("catalogo"))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "login":
            usuario = request.form.get("usuario", "").strip()
            senha = request.form.get("senha", "").strip()

            user = db.autenticar(usuario, senha)
            if not user:
                flash("Usuário ou senha inválidos.", "danger")
                return redirect(url_for("index"))

            session["usuario"] = {
                "id": user["id"],
                "nome": user["nome"],
                "usuario": user["usuario"],
                "perfil": user["perfil"],
            }
            session.setdefault("carrinho", {})
            flash(f"Bem-vindo, {user['nome']}!", "success")

            if user["perfil"] in ["dono", "funcionario"]:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("catalogo"))

        if acao == "cadastro":
            nome = request.form.get("nome", "").strip()
            usuario = request.form.get("novo_usuario", "").strip()
            senha = request.form.get("nova_senha", "").strip()

            if not nome or not usuario or not senha:
                flash("Preencha nome, usuário e senha para criar a conta.", "warning")
                return redirect(url_for("index"))

            ok, mensagem = db.criar_cliente(nome, usuario, senha)
            flash(mensagem, "success" if ok else "danger")
            return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    resumo = db.resumo_admin()
    produtos = db.buscar_produtos()
    pedidos = db.pedidos_gerais()
    return render_template("admin/dashboard.html", resumo=resumo, produtos=produtos, pedidos=pedidos)


@app.route("/admin/produtos/novo", methods=["GET", "POST"])
@admin_required
def admin_novo_produto():
    db = get_db()
    if request.method == "POST":
        try:
            db.adicionar_produto(
                request.form.get("nome", ""),
                request.form.get("preco", 0),
                request.form.get("categoria", ""),
                request.form.get("estoque", 0),
                request.form.get("descricao", ""),
            )
            flash("Produto cadastrado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))
        except Exception:
            flash("Não foi possível cadastrar o produto. Verifique os campos.", "danger")

    return render_template("admin/produto_form.html", produto=None)


@app.route("/admin/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@admin_required
def admin_editar_produto(produto_id):
    db = get_db()
    produto = db.buscar_produto_por_id(produto_id)
    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        try:
            db.atualizar_produto(
                produto_id,
                request.form.get("nome", ""),
                request.form.get("preco", 0),
                request.form.get("categoria", ""),
                request.form.get("estoque", 0),
                request.form.get("descricao", ""),
            )
            flash("Produto atualizado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))
        except Exception:
            flash("Não foi possível atualizar o produto. Verifique os campos.", "danger")

    return render_template("admin/produto_form.html", produto=produto)


@app.post("/admin/produtos/<int:produto_id>/excluir")
@admin_required
def admin_excluir_produto(produto_id):
    db = get_db()
    produto = db.buscar_produto_por_id(produto_id)
    if not produto:
        flash("Produto não encontrado.", "danger")
    else:
        db.remover_produto(produto_id)
        flash("Produto removido com sucesso.", "info")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/pedidos/<int:pedido_id>")
@admin_required
def admin_detalhe_pedido(pedido_id):
    db = get_db()
    itens = db.itens_pedido(pedido_id)
    if not itens:
        flash("Pedido não encontrado ou sem itens.", "warning")
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/pedido_detalhe.html", pedido_id=pedido_id, itens=itens)


@app.route("/catalogo")
@login_required
def catalogo():
    usuario = session.get("usuario")
    if usuario["perfil"] in ["dono", "funcionario"]:
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    busca = request.args.get("busca", "")
    categoria = request.args.get("categoria", "Todas")
    produtos = db.buscar_produtos(busca=busca, categoria=categoria)
    categorias = ["Todas"] + db.categorias()
    return render_template(
        "cliente/catalogo.html",
        produtos=produtos,
        categorias=categorias,
        busca=busca,
        categoria_atual=categoria,
    )


@app.post("/carrinho/adicionar/<int:produto_id>")
@login_required
def adicionar_carrinho(produto_id):
    usuario = session.get("usuario")
    if usuario["perfil"] in ["dono", "funcionario"]:
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    produto = db.buscar_produto_por_id(produto_id)
    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for("catalogo"))

    try:
        quantidade = int(request.form.get("quantidade", 1))
    except ValueError:
        quantidade = 1

    if quantidade <= 0:
        flash("A quantidade precisa ser maior que zero.", "warning")
        return redirect(url_for("catalogo"))

    carrinho = session.get("carrinho", {})
    chave = str(produto_id)
    quantidade_atual = int(carrinho.get(chave, {}).get("quantidade", 0))
    nova_quantidade = quantidade_atual + quantidade

    if nova_quantidade > produto["estoque"]:
        flash(f"Estoque insuficiente para {produto['nome']}.", "danger")
        return redirect(url_for("catalogo"))

    carrinho[chave] = {
        "produto_id": produto["id"],
        "nome": produto["nome"],
        "preco": float(produto["preco"]),
        "quantidade": nova_quantidade,
        "subtotal": round(float(produto["preco"]) * nova_quantidade, 2),
    }
    session["carrinho"] = carrinho
    flash(f"{produto['nome']} adicionado ao carrinho.", "success")
    return redirect(url_for("catalogo"))


@app.route("/carrinho")
@login_required
def ver_carrinho():
    usuario = session.get("usuario")
    if usuario["perfil"] in ["dono", "funcionario"]:
        return redirect(url_for("admin_dashboard"))

    carrinho = session.get("carrinho", {})
    itens = list(carrinho.values())
    total = sum(float(item["subtotal"]) for item in itens)
    return render_template("cliente/carrinho.html", itens=itens, total=total)


@app.post("/carrinho/remover/<int:produto_id>")
@login_required
def remover_carrinho(produto_id):
    carrinho = session.get("carrinho", {})
    chave = str(produto_id)
    if chave in carrinho:
        nome = carrinho[chave]["nome"]
        carrinho.pop(chave)
        session["carrinho"] = carrinho
        flash(f"{nome} removido do carrinho.", "info")
    return redirect(url_for("ver_carrinho"))


@app.post("/checkout")
@login_required
def checkout():
    usuario = session.get("usuario")
    if usuario["perfil"] in ["dono", "funcionario"]:
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    carrinho = session.get("carrinho", {})
    ok, mensagem = db.criar_pedido(usuario["id"], carrinho)
    flash(mensagem, "success" if ok else "danger")
    if ok:
        session["carrinho"] = {}
    return redirect(url_for("meus_pedidos" if ok else "ver_carrinho"))


@app.route("/meus-pedidos")
@login_required
def meus_pedidos():
    usuario = session.get("usuario")
    if usuario["perfil"] in ["dono", "funcionario"]:
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    pedidos = db.pedidos_cliente(usuario["id"])

    pedidos_com_itens = []
    for pedido in pedidos:
        pedidos_com_itens.append({"pedido": pedido, "itens": db.itens_pedido(pedido["id"])})

    return render_template("cliente/pedidos.html", pedidos_com_itens=pedidos_com_itens)


if __name__ == "__main__":
    app.run(debug=True)
