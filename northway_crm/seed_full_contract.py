from app import create_app
from models import db, ContractTemplate, Company
import markdown

app = create_app()

# Markdown content provided by user
markdown_content = """
**CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE GESTÃO DE MARKETING E OUTRAS AVENÇAS**

Pelo presente instrumento particular, as partes abaixo nomeadas e qualificadas, a saber:

**{{CONTRATANTE_NOME_EMPRESARIAL}}**, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº **{{CONTRATANTE_CNPJ}}**, com sede na **{{CONTRATANTE_ENDERECO}}**, representada neste ato por **{{CONTRATANTE_REPRESENTANTE_LEGAL}}**, inscrito no CPF nº **{{CONTRATANTE_CPF}}**, residente e domiciliado **{{CONTRATANTE_ENDERECO_REPRESENTANTE}}**, doravante e simplesmente denominada **CONTRATANTE**

**{{CONTRATADA_NOME_EMPRESARIAL}}**, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº **{{CONTRATADA_CNPJ}}**, com sede na **{{CONTRATADA_ENDERECO}}**, representada neste ato por **{{CONTRATADA_REPRESENTANTE_LEGAL}}**, inscrito no CPF nº **{{CONTRATADA_CPF}}**, residente e domiciliado **{{CONTRATADA_ENDERECO_REPRESENTANTE}}**, doravante e simplesmente denominada **CONTRATADA**.

Têm justo e contratado, na melhor forma de direito, firmar o presente contrato de prestação de serviços, nos termos e condições a seguir:

**CLÁUSULA PRIMEIRA - DO OBJETO**

O objeto do presente instrumento é a prestação, pela **CONTRATADA**, à **CONTRATANTE** de Pesquisa de Mercado e Concorrência, Gestão de Redes Sociais (Instagram/Facebook), Gestão de Tráfego Pago, desenvolvimento de estratégias e ações de marketing integradas, visando à consolidação de imagem, de marca e produtos, conforme detalhado na Proposta Anexa, emitida em **{{DATA_PROPOSTA}}**.

Situações excepcionais que demandem custos com deslocamento, hospedagem e alimentação para prestação de serviços, poderão ocorrer, desde que previamente acordadas entre as Partes e devidamente justificadas. Tais custos serão documentados e detalhados em relatório de prestação de contas.

**CLÁUSULA SEGUNDA - DAS RESPONSABILIDADES DAS PARTES**

2. A **CONTRATANTE** compromete-se e responsabiliza-se à:

Efetuar os pagamentos na forma e nos prazos determinados neste Contrato, na forma prescrita na cláusula 5.1;
Disponibilizar todo e qualquer, material escrito, documento ou informação atinente aos serviços a serem prestados, que venham a ser solicitados pela **CONTRATADA**, que estejam à sua disposição, ou obtê-los com terceiros que os detenha, incluindo e não se limitando à indicação de login e senha de acesso a qualquer plataforma, tais como facebook, instagram e/ou plataforma de vendas;
A **CONTRATANTE** será a única e exclusiva responsável pela idoneidade das informações, dados, declarações ou documentos enviados à **CONTRATADA**, não tendo esta qualquer responsabilidade por eles, salvo quando por ela expedidos;
Nomear um representante legal, com indicação de e-mail e telefone, para acompanhar o trabalho da **CONTRATADA**, bem como manter contato sempre que necessário;
Responder a todos os questionamentos da **CONTRATADA** dentro de um período máximo de 48h, sob pena de concordância tácita, tudo com objetivo de evitar atrasos ou interrupções dos prazos estabelecidos no cronograma a ser desenvolvido;
Confiar absolutamente nas estratégias traçadas e apresentadas pela **CONTRATADA** para todos os conteúdos a serem desenvolvidas durante a vigência deste contrato, ficando acordado desde já que todo o material e conteúdo a ser elaborado e as ações desenvolvidas poderão ser discutidas previamente entre ambas as partes, mas a decisão final sobre os pontos acima expostos caberá exclusivamente à **CONTRATADA**.
Pagamento integral dos custos referentes às plataformas digitais utilizadas no projeto, incluindo: plataforma de hospedagem de websites, plataforma de anúncios para distribuição de conteúdo, tráfego e captação de leads, plataformas de pagamento, plataformas de programação de publicações em redes sociais, hospedagem e deslocamento para reuniões ou encontros presenciais, contratação de terceiros, entre outros, sendo que todos os custos deverão ser discutidos previamente entre as partes;
Encargos e taxas dos serviços de recebimentos de pagamentos e das operadoras de cartões de crédito;
Custos com plataformas de distribuição de anúncios na internet (tráfego pago), ficando acordado previamente um valor mínimo de **{{VALOR_MINIMO_TRÁFEGO}}** por mês pelo período de **{{PERIODO_TRÁFEGO}}**, podendo haver variações de acordo com o mercado;
Compra e renovação de domínios da internet;
Seguir as orientações enviadas pela **CONTRATADA** sobre questões técnicas relacionadas à produção e gravação dos materiais audiovisuais, bem como, da elaboração de demais conteúdos e materiais;
Sugerir todo e qualquer conteúdo informativo de suas páginas, sendo esta integralmente responsável pelos efeitos provenientes destas informações, respondendo civil e criminalmente por atos contrários à lei, propaganda enganosa, atos obscenos e violação de direitos autorais;
Arcar com todas as taxas, impostos e/ou encargos governamentais devidos em decorrência, direta ou indireta, deste instrumento e de sua execução, bem como com gastos com empresas de contabilidade e afins;
Realizar o pagamento dos valores dentro do prazo acordado, sob pena de multa, conforme cláusula quinta.
Tráfego Pago nas plataformas de anúncios na internet pré-determinados na estratégia, como por exemplo, Facebook Ads e Instagram Ads, realizando coleta de dados para análise de métricas e otimização das campanhas de maneira contínua.

O orçamento destinado para tráfego será discutido e apresentado formalmente, devendo ser aprovado previamente pela **CONTRATANTE**, obedecendo irrefutavelmente às condições expostas na **CLÁUSULA SEGUNDA**, Parágrafo 2.1, item “e”.
Não há qualquer vínculo ou responsabilidade por parte da **CONTRATADA** sobre o pagamento dos anúncios e serviços contratados dentro de tais plataformas, que devem ser realizados de acordo com o orçamento estipulado previamente e que devem ser pagos exclusivamente pela **CONTRATANTE**.

Pagamento integral dos custos referentes à equipe, profissionais e equipamentos para realização de todas as responsabilidades descritas nos itens anteriores deste parágrafo;
q) Não utilizar nenhum recurso financeiro da **CONTRATANTE**, mesmo que para fins de sua responsabilidade, sem sua prévia e expressa autorização;
n) Informar imediatamente à **CONTRATANTE** qualquer acontecimento ordinário e/ou extraordinário que venha a ocorrer durante a prestação dos Serviços;

2.1 A **CONTRATADA** compromete-se e responsabiliza-se à:

A **CONTRATADA** se compromete a empregar seus melhores esforços na execução dos serviços de marketing, utilizando técnicas e estratégias adequadas ao segmento da **CONTRATANTE**.
Atender prontamente as sugestões e exigências da **CONTRATANTE**, refazendo e corrigindo, quando for o caso.
Manter durante a execução do Contrato, em compatibilidade com as obrigações assumidas todas as condições de habilitação e qualificação exigidas para a execução do Contrato.
Solicitar à **CONTRATANTE** eventuais informações e dados necessários para execução dos serviços, bem como orientá-la sobre os procedimentos relacionados ao presente Contrato que sejam de responsabilidade desta;
Fornecer, sempre que solicitado pela **CONTRATANTE**, informações e prévias sobre os serviços prestados, se obrigando de igual maneira, a emitir relatórios com periodicidade formalmente definida entre as Partes, devidamente detalhados, contendo um resumo dos trabalhados, atividades realizadas, e os resultados obtidos, de modo a permitir à **CONTRATANTE** o acompanhamento e a avaliação contínua dos serviços prestados.
A supervisão, fiscalização, orientação e direção técnica e administrativa dos profissionais envolvidos na execução dos serviços ora contratados;
Emitir à **CONTRATANTE** os boletos referentes a Prestação de Serviços por ocasião dos pagamentos;
Receber, arquivar e responsabilizar-se pelos documentos/informações eventualmente recebidos da **CONTRATANTE**, reservando sua propriedade para esta. A **CONTRATADA** responsabiliza-se pela guarda e devido sigilo (quando aplicável) dos documentos materiais, disponibilizando-os à **CONTRATANTE** sempre que solicitado;

2.2 Em caso de responsabilidades omissas ou complementares de quaisquer uma das partes, essas poderão constar em termo aditivo que após assinado entre as partes integrarão o presente instrumento.

**CLÁUSULA TERCEIRA - DO PRAZO**

3.1. Conforme estipulado pelas Partes, a prestação dos serviços mencionados na cláusula 1.1. terá inicio em **{{DATA_INICIO}}** e término previsto em **{{DATA_TERMINO}}**.

3.2. O prazo estimado acima poderá ser revisado, mediante acordo entre as partes, desde que seja formalizado por meio de aditivo.

**CLÁUSULA QUARTA - DA GARANTIA**

**CONTRATADA** não garante resultados específicos, faturamento mínimo, retorno financeiro ou qualquer outro tipo de performance, uma vez que ações de marketing são influenciadas por fatores externos, como concorrência, sazonalidade, condições de mercado, qualidade do produto/serviço da **CONTRATANTE**, entre outros, que fogem ao seu controle.

A **CONTRATANTE** reconhece e aceita que os serviços contratados são de meio e não de fim, ou seja, a **CONTRATADA** obriga-se à correta execução das ações de marketing, mas não a um resultado específico.

**CLÁUSULA QUINTA – DO PREÇO E FORMA DE PAGAMENTO**

Em remuneração aos serviços a serem prestados pela **CONTRATADA** sob o presente Contrato, previstos na cláusula 1.1, a **CONTRATANTE** concorda e se obriga a pagar o valor total de **{{VALOR_TOTAL_CONTRATO}}**, na seguinte forma:

A parcela única no valor de **{{VALOR_IMPLANTACAO}}** referente a implantação daas ferramentas de uso.
**{{NUMERO_PARCELAS}}** parcelas no valor de **{{VALOR_PARCELA}}** mensalmente, a serem pagas todo o dia **{{DIA_VENCIMENTO}}** de cada mês.

Os pagamentos deverão ser realizados por meio de boleto bancário, o qual disponibilizará, adicionalmente, a opção de quitação via PIX.

O atraso no pagamento de qualquer parcela implicará na aplicação de:

Multa moratória de 2% (dois por cento) sobre o valor em atraso;
Juros de mora de 1% (um por cento) ao mês, calculados pro rata die;
Possibilidade de negativação do nome da **CONTRATANTE** em órgãos de proteção ao crédito (SPC, Serasa e similares), caso o atraso ultrapasse 5 (cinco) dias, independentemente de notificação prévia
Correção monetária pelo IPCA (Índice de Preços ao Consumidor Amplo), caso o atraso ultrapasse 30 dias.
Em caso de inadimplência superior a 30 (trinta) dias, a **CONTRATADA** poderá, a seu exclusivo critério:
Suspender imediatamente a prestação dos serviços até a regularização dos pagamentos;
Rescindir o contrato, aplicando-se às penalidades previstas na Cláusula de Rescisão.

Caso a **CONTRATANTE** identifique qualquer irregularidade na Fatura/Cobrança, deverá comunicar à **CONTRATADA** no prazo máximo de 48 horas após o recebimento, especificando detalhadamente a inconsistência. O prazo para pagamento será prorrogado somente pelo período necessário para a correção da fatura, sem prejuízo dos encargos por atraso caso a contestação seja infundada.

O valor especificado na Cláusula 5.1 é fixo e incluem todos os encargos sociais, trabalhistas, previdenciários, securitários, taxas de administração, impostos e tributos de qualquer natureza, não sendo devido qualquer valor adicional à **CONTRATADA** além do estipulado neste contrato.

Os boletos bancários, faturas ou links de pagamento referentes às parcelas deste contrato serão enviados pela **CONTRATADA** ao endereço de e-mail e/ou número de telefones informados pela **CONTRATANTE**.

**CLÁUSULA SEXTA - DA PROPRIEDADE INTELECTUAL**

6.1 Todas as informações técnicas, mercadológicas ou de propriedade intelectual ou industrial fornecidas, ou de qualquer forma reveladas de uma Parte à outra, nos termos e para os fins deste Contrato, seja por escrito ou verbalmente, serão consideradas de propriedade exclusiva da Parte divulgadora, e assim permanecerão, obrigando-se a Parte receptora a não registrar, nem tentar o registro, direta ou indiretamente, em qualquer localidade do país ou do exterior, de quaisquer patentes, marcas, nomes, direitos autorais ou quaisquer outros direitos de propriedade industrial ou intelectual, que sejam ou venham a ser de propriedade da Parte divulgadora, por força deste Contrato.

6.2. As Partes declaram e concordam expressamente que o presente Contrato não implica em aquisição, cessão ou permissão de comercialização de quaisquer marcas, patentes, invenções ou modelos de utilidade pertencente à outra Parte, sendo certo que não adquiriu, nem irá adquirir, qualquer direito de propriedade sobre tais bens.

**CLÁUSULA SÉTIMA - RESPONSABILIDADES DAS PARTES**

Ambas as Partes reconhecem expressamente não haver qualquer vínculo societário e/ou empregatício entre as Partes contratantes, seus representantes legais, prepostos, empregados, empregados de empresas subcontratadas ou terceiros utilizados no cumprimento das obrigações contratadas à outra Parte.

No caso de ação judicial ajuizada por qualquer terceiro em face da outra Parte, inclusive ações trabalhistas ajuizadas em face desta pelos empregados da Parte responsável, ou quaisquer outras pessoas alocadas para os serviços, a Parte Responsável/Infratora terá a obrigação de substituir a Parte Inocente nos respectivos processos, desde que tais reivindicações sejam decorrentes deste Contrato ou dos serviços prestados e que sejam comprovadamente decorrentes de responsabilidade da Parte qualificada como Infratora.

7.2.1. Na impossibilidade de substituição, ou caso a Parte Responsável/Infratora deixe de agir para a defesa de tais reclamações ou ações, a Parte Inocente poderá tomar as medidas legais apropriadas, obrigando-se a Parte Responsável a ressarcir a Parte Inocente, no prazo de 15 (quinze) dias úteis, de todo e qualquer valor que seja incorrido por esta em virtude de sua defesa e condenação, incluindo custas e honorários advocatícios, sendo que no caso de condenação o respectivo valor somente será devido após decisão judicial com trânsito em julgado.

Fica expressamente estipulado que não se estabelece, por força deste Contrato, qualquer vínculo empregatício ou de responsabilidade por qualquer das Partes para com os empregados, prepostos, contratados ou representantes, a qualquer título, da outra Parte, cabendo a cada uma das Partes a responsabilidade, como empregadora ou responsável pela subcontratação, por todas as despesas, obrigações e encargos decorrentes da legislação em vigor para com seus respectivos empregados e contratados a qualquer título.

A inadimplência de quaisquer das Partes, com referência às despesas especificadas nos itens acima, não transfere à Parte Inocente a responsabilidade de seu pagamento, nem poderá onerar o objeto do Contrato.

**CLÁUSULA OITAVA - DA CONFIDENCIALIDADE**

Todas as informações trocadas entre as partes no âmbito deste contrato são consideradas estritamente confidenciais e não poderão ser divulgadas a terceiros sem o consentimento prévio e por escrito da outra parte, salvo quando exigido por lei. Caso seja necessária a apresentação deste contrato a órgãos governamentais, a parte responsável pela apresentação deverá notificar a outra previamente, anexando a comprovação da exigência legal.

A **CONTRATANTE** compromete-se a manter sob sigilo todas as informações estratégicas, comerciais e operacionais obtidas da **CONTRATADA** durante a vigência do contrato e após sua rescisão, não podendo repassá-las a terceiros sem autorização expressa.

**CLÁUSULA NONA - PROTEÇÃO DE DADOS**

9.1.  As partes obrigam-se a estar em conformidade com a legislação sobre privacidade e proteção de dados vigente, em particular a Lei Federal n. 13.709/2018 (“LGPD”), assumindo integral responsabilidade por toda operação de tratamento de dados pessoais, desde a coleta, tratamento, armazenamento e eliminação, assegurando que o tratamento dos dados pessoais seja realizado de acordo com as finalidades específicas e consentidas pelos titulares, nos termos da legislação vigente e da LGPD.  As partes obrigam-se, ainda, a não ceder ou compartilhar a qualquer título com terceiros os dados pessoais a que tiverem acesso sem finalidade legítima ou em desacordo com a lei, observando sua privacidade e proteção, tratando os dados pessoais coletados para fins lícitos e expressamente previstos em lei, empregando as melhores práticas e medidas de segurança técnicas e administrativas aptas a proteger os dados pessoais de acessos não autorizados e de qualquer forma de tratamento inadequado ou ilícito.

9.2. As partes, ainda, se comprometem a tratar os dados pessoais coletados por este instrumento para a finalidade exclusiva de operacionalizar o objeto contratual.

9.3. As partes informam que poderão compartilhar os dados pessoais envolvidos no presente Contrato para cumprimento de obrigações legais ou regulatórias, atendimento de solicitações judiciais e administrativas ou para operacionalizar a prestação de serviço e/ou produto contratado, comprometendo-se a não compartilhar dados pessoais desnecessariamente ou em desconformidade com a legislação.

**CLÁUSULA DÉCIMA - DA RESCISÃO E PENALIDADES**

10.1. O presente contrato poderá ser rescindido por qualquer das partes em caso de descumprimento de obrigação contratual, desde que a parte inadimplente não regularize a situação no prazo de 5 (cinco) dias após o recebimento de notificação formal enviada por e-mail.

10.2. A parte que der causa à rescisão do presente contrato, por descumprir qualquer cláusula acordada, arcará com uma penalidade financeira correspondente a 50% (cinquenta por cento) do valor total do contrato, devidamente corrigido monetariamente com base no IGP-M, acrescido de juros de mora de 1% (um por cento) ao mês, contados a partir da data da infração, além de perdas e danos a serem apurados e despesas processuais e advocatícias, caso necessário. O disposto no item 8.2 passa a vigorar após o período de experiência de 30 (trinta) dias contados da assinatura deste contrato. Durante esse período, qualquer uma das partes poderá rescindir o contrato de forma unilateral, sem necessidade de justificativa, sem incidência de penalidades.

10.3. Caso o **CONTRATANTE** solicite o cancelamento do presente contrato antes da conclusão dos serviços contratados, ficará obrigado ao pagamento de uma multa compensatória correspondente a 50% (cinquenta por cento) do valor total do contrato, além do pagamento integral de eventuais valores devidos pelos serviços já prestados até a data da rescisão. Em nenhuma hipótese haverá devolução de valores já pagos pelo **CONTRATANTE** à **CONTRATADA**, independentemente do motivo da rescisão.

10.4. A rescisão somente será efetivada mediante o pagamento integral da multa estipulada. O não pagamento da multa dentro do prazo de 5 (cinco) dias a partir da solicitação de cancelamento poderá resultar na adoção de medidas judiciais e extrajudiciais para a devida cobrança, incluindo a incidência de juros, correção monetária e honorários advocatícios de 20% (vinte por cento) sobre o valor total devido.

10.5. A **CONTRATADA** poderá rescindir o contrato a qualquer tempo, caso o **CONTRATANTE** descumpra suas obrigações, sem que haja qualquer ônus para a **CONTRATADA** e sem prejuízo da aplicação de penalidades cabíveis. Fica expressamente acordado que, em nenhuma hipótese, a **CONTRATADA** estará sujeita a qualquer forma de reembolso, indenização ou penalidade financeira decorrente da rescisão contratual, independentemente do motivo.

**CLÁUSULA DÉCIMA PRIMEIRA - DISPOSIÇÕES GERAIS**

11.1. A **CONTRATADA** obriga-se, durante a vigência deste contrato, a conduzir seus serviços de forma ética, em conformidade com a legislação vigente e os preceitos legais aplicáveis. A **CONTRATADA** declara e garante que conhece e aceita integralmente as disposições das leis anticorrupção aplicáveis, incluindo, mas não se limitando, à Lei nº 12.846/2013 (Lei Anticorrupção Brasileira), comprometendo-se a não praticar, direta ou indiretamente, quaisquer atos que possam ser caracterizados como ilícitos nos termos dessas normas.

11.2. As partes acordam que a **CONTRATADA** poderá utilizar, conforme sua conveniência, quaisquer materiais produzidos durante a vigência deste contrato para fins de promoção própria e composição de portfólio, com a necessidade de prévia autorização da **CONTRATANTE**, salvo disposição expressa em contrário.

11.3. O fato de qualquer uma das partes, por mera liberalidade, deixar de exigir o cumprimento de qualquer cláusula ou obrigação prevista neste contrato não será considerado novação, renúncia de direitos, alteração contratual ou criação de precedente, podendo a parte exigir o cumprimento da obrigação a qualquer tempo.

11.4. O presente contrato não poderá ser cedido, transferido ou subcontratado, no todo ou em parte, por qualquer das partes, sem o consentimento prévio e expresso da outra parte, sob pena de nulidade.

11.5. As partes não serão responsabilizadas pelo descumprimento, total ou parcial, deste contrato quando tal descumprimento decorrer de caso fortuito ou força maior, nos termos do artigo 393 do Código Civil. Em tais circunstâncias, não será devida qualquer compensação, reembolso ou indenização, devendo as partes envidar esforços razoáveis para minimizar os impactos e retomar o cumprimento contratual assim que possível.

11.6. O presente contrato obriga não apenas as partes signatárias, mas também seus herdeiros, sucessores e representantes legais, independentemente do motivo da sucessão.

11.7. Nenhuma alteração deste contrato será válida se não for formalizada por escrito e assinada por ambas as partes mediante instrumento de aditivo contratual.

Caso qualquer disposição deste contrato venha a ser declarada nula, anulável ou inexequível por decisão judicial, ou administrativa, as demais disposições permanecerão plenamente válidas e exequíveis. Se necessário, as partes se comprometem a substituir a cláusula afetada por outra que atinja o mesmo objetivo e que esteja em conformidade com a legislação aplicável.

O presente Contrato se constitui em título executivo extrajudicial, nos termos do artigo 784, inciso III, do Código de Processo Civil, quando assinado de forma física e pelo §4° do mesmo dispositivo, quando assinado de forma eletrônica.

As Partes e as testemunhas envolvidas neste instrumento afirmam e declaram que o Contrato poderá ser assinado de forma eletrônica, com fundamento na Lei 14.063/2020 e no Decreto 10.278/2020, sendo as assinaturas consideradas válidas, vinculantes e executáveis, desde que firmadas pelos representantes legais das Partes.

11.10.1. Consigna-se no presente instrumento que a assinatura com Certificado Digital/eletrônica tem a mesma validade jurídica de um registro e autenticação feita em cartório, seja mediante utilização de certificados e-CPF, e-CNPJ e/ou NF-e. As Partes renunciam à possibilidade de exigir a troca, envio ou entrega das vias originais (não-eletrônicas) assinadas do instrumento, bem como renunciam ao direito de recusar ou contestar a validade das assinaturas eletrônicas, na medida máxima permitida pela legislação aplicável.

**CLÁUSULA DÉCIMA SEGUNDA - DO FORO**

12.1. Fica eleito o Foro da Comarca de **{{FORO_COMARCA}}**, **{{FORO_ESTADO}}**, para dirimir todas e quaisquer dúvidas oriundas deste contrato, com renúncia de qualquer outro por mais privilegiado que seja.

E por estarem concordes, assinam o presente contrato em **{{NUMERO_VIAS}}** vias de igual teor e forma, na presença de 02 (duas) testemunhas, para que este opere seus regulares e jurídicos efeitos.

**{{CIDADE_ASSINATURA}}**, **{{DATA_ASSINATURA}}**.

**___________________________________**               **___________________________________**
**{{CONTRATANTE_ASSINATURA_NOME}}**                 **{{CONTRATADA_ASSINATURA_NOME}}**
CNPJ **{{CONTRATANTE_CNPJ}}**                     CNPJ **{{CONTRATADA_CNPJ}}**


Testemunhas:

___________________________________
Nome: **{{TESTEMUNHA1_NOME}}**
CPF: **{{TESTEMUNHA1_CPF}}**

___________________________________
Nome: **{{TESTEMUNHA2_NOME}}**
CPF: **{{TESTEMUNHA2_CPF}}**
"""

# Convert Markdown to HTML to ensure variables and formatting work
html_content = markdown.markdown(markdown_content)

with app.app_context():
    companies = Company.query.all()
    
    for company in companies:
        # Check duplicates
        template = ContractTemplate.query.filter_by(company_id=company.id, name="contrato - teste").first()
        if not template:
            template = ContractTemplate(
                company_id=company.id,
                name="contrato - teste",
                type="contract",
                content=html_content,
                active=True
            )
            db.session.add(template)
            print(f"Created 'contrato - teste' for {company.name}")
        else:
            # Update content
            template.content = html_content
            print(f"Updated 'contrato - teste' for {company.name}")
            
    db.session.commit()
