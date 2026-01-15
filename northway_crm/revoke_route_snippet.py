@master.route('/master/revoke-self')
@login_required
def revoke_self():
    """
    Temporary route to allow the user to demote themselves.
    """
    if current_user.email == 'marciogholmm@gmail.com':
        current_user.is_super_admin = False
        current_user.role = 'admin' # Ensure lowercase 'admin' as per our new standard
        db.session.commit()
        return "Sucesso: Acesso Super Admin removido. Você agora é um Admin da Empresa. <a href='/'>Voltar</a>"
    return "Acesso negado."
