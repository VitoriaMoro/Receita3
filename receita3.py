import streamlit as st
import requests
from PIL import Image
import io
from deep_translator import GoogleTranslator 

# Configuração do tradutor
translator_pt_en = lambda text: GoogleTranslator(source='pt', target='en').translate(text)
translator_en_pt = lambda text: GoogleTranslator(source='en', target='pt').translate(text)
session = requests.Session()

# Função para traduzir dados de receitas (MODIFICADA)
def translate_recipe_data(recipe_data):
    try:
        # Traduz campos principais
        recipe_data['strMeal'] = translator_en_pt(recipe_data.get('strMeal', ''))
        recipe_data['strCategory'] = translator_en_pt(recipe_data.get('strCategory', ''))
        recipe_data['strArea'] = translator_en_pt(recipe_data.get('strArea', ''))
        recipe_data['strInstructions'] = translator_en_pt(recipe_data.get('strInstructions', ''))
        
        # Traduz ingredientes E medidas
        for i in range(1, 21):
            # Traduz ingredientes
            ingredient_key = f'strIngredient{i}'
            if recipe_data.get(ingredient_key) and recipe_data[ingredient_key].strip():
                recipe_data[ingredient_key] = translator_en_pt(recipe_data[ingredient_key].strip())
            
            # Traduz medidas (NOVO)
            measure_key = f'strMeasure{i}'
            if recipe_data.get(measure_key) and recipe_data[measure_key].strip():
                recipe_data[measure_key] = translator_en_pt(recipe_data[measure_key].strip())
                
        return recipe_data
    except Exception as e:
        st.error(f"Erro na tradução: {e}")
        return recipe_data

# Função para buscar receitas por ingredientes (MODIFICADA)
def get_recipes_by_matching_ingredients(user_ingredients, area=None, max_recipes=10):
    # Traduz ingredientes para inglês
    translated_ingredients = [translator_pt_en(ing.lower().strip()) for ing in user_ingredients]
    
    recipe_ids = set()
    for ingredient in translated_ingredients:
        try:
            response = session.get(
                f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
            )
            data = response.json()
            if data.get('meals'):
                for meal in data['meals']:
                    recipe_ids.add(meal['idMeal'])
        except (requests.exceptions.RequestException, TypeError):
            continue

    if not recipe_ids:
        return []

    recipes = []
    for recipe_id in list(recipe_ids)[:50]:
        try:
            response = session.get(
                f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={recipe_id}"
            )
            recipe_data = response.json()['meals'][0]
            
            # Traduz dados da receita para português
            recipe_data = translate_recipe_data(recipe_data)

            if area and area != "Todos" and recipe_data.get('strArea') != area:
                continue

            # Armazena ingredientes com medidas (MODIFICADO)
            recipe_ingredients_with_measures = []
            for i in range(1, 21):
                ingredient_key = f'strIngredient{i}'
                measure_key = f'strMeasure{i}'
                
                if recipe_data.get(ingredient_key) and recipe_data[ingredient_key].strip():
                    ingredient = recipe_data[ingredient_key].strip().lower()
                    measure = recipe_data.get(measure_key, '').strip()
                    
                    # Combina medida e ingrediente
                    recipe_ingredients_with_measures.append(f"{measure} {ingredient}")

            # Verifica correspondência com ingredientes originais (em português)
            matches = sum(1 for ing_pair in recipe_ingredients_with_measures 
                         if any(orig_ing.lower() in ing_pair for orig_ing in user_ingredients))
            total_ingredients = len(recipe_ingredients_with_measures)

            recipe_object = {
                'data': recipe_data,
                'ingredients': recipe_ingredients_with_measures,  # AGORA CONTÉM MEDIDAS
                'matches': matches,
                'total': total_ingredients
            }
            recipes.append(recipe_object)
            st.session_state.all_recipes_data[recipe_id] = recipe_object

        except (requests.exceptions.RequestException, KeyError, IndexError, TypeError) as e:
            continue

    recipes.sort(key=lambda x: x['matches'], reverse=True)
    return recipes[:max_recipes]

# Função para buscar receitas por país
def get_recipes_by_area(area):
    try:
        response = session.get(
            f"https://www.themealdb.com/api/json/v1/1/filter.php?a={area}"
        )
        data = response.json()
        if not data.get('meals'):
            return []
            
        # Obtém detalhes completos e traduz cada receita
        detailed_recipes = []
        for meal in data['meals'][:5]:
            recipe_response = session.get(
                f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal['idMeal']}"
            )
            recipe_data = recipe_response.json()['meals'][0]
            detailed_recipes.append(translate_recipe_data(recipe_data))
        
        return detailed_recipes
    except requests.exceptions.RequestException:
        return []

# Função para buscar lista de países (traduzida)
def get_areas():
    try:
        response = session.get(
            "https://www.themealdb.com/api/json/v1/1/list.php?a=list"
        )
        data = response.json()
        areas = ["Todos"] + sorted([area['strArea'] for area in data['meals']])
        
        # Traduz nomes dos países
        translated_areas = ["Todos"]
        for area in areas[1:]:
            try:
                translated_areas.append(translator_en_pt(area))
            except:
                translated_areas.append(area)
                
        return translated_areas
    except requests.exceptions.RequestException:
        return ["Todos"]

# Função para exibir receitas (MODIFICADA para mostrar medidas)
def display_recipe(recipe, user_ingredients, is_main=False):
    recipe_data = recipe['data']
    recipe_id = recipe_data['idMeal']

    title_html = f"<h3 style='font-size:24px; margin-bottom:10px;'>{recipe_data['strMeal']}</h3>"
    st.markdown(title_html, unsafe_allow_html=True)

    with st.expander("", expanded=is_main):
        if recipe_data.get('strMealThumb'):
            try:
                response_img = requests.get(recipe_data['strMealThumb'])
                img = Image.open(io.BytesIO(response_img.content))
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(img, caption=recipe_data['strMeal'], width=240)
            except:
                st.warning("Não foi possível carregar a imagem da receita")

        st.caption(f"🎯 Compatibilidade: {recipe['matches']}/{recipe['total']} ingredientes")
        st.progress(recipe['matches'] / recipe['total'])
        st.caption(f"🗂️ Categoria: {recipe_data.get('strCategory', 'N/A')}")
        st.caption(f"🌍 Cozinha: {recipe_data.get('strArea', 'N/A')}")

        col1, col2 = st.columns(2)
        if recipe_data.get('strSource'):
            col1.markdown(f"🔗 [Receita Original]({recipe_data['strSource']})")
        if recipe_data.get('strYoutube'):
            col2.markdown(f"📺 [Vídeo no YouTube]({recipe_data['strYoutube']})")

        st.subheader("📋 Ingredientes:")
        # Agora exibe medida + ingrediente (MODIFICADO)
        for ing_pair in recipe['ingredients']:
            match_indicator = "✅" if any(orig_ing.lower() in ing_pair for orig_ing in user_ingredients) else "❌"
            st.markdown(f"{match_indicator} {ing_pair.capitalize()}")

        st.subheader("👩‍🍳 Instruções:")
        st.write(recipe_data['strInstructions'])
        
        current_rating = st.session_state.user_ratings.get(recipe_id, 0)
        new_rating = st.slider(
            "Avalie esta receita:",
            1, 5, current_rating,
            key=f"rate_{recipe_id}_{is_main}"
        )

        if st.button("Salvar Avaliação", key=f"btn_rate_{recipe_id}_{is_main}"):
            st.session_state.user_ratings[recipe_id] = new_rating
            st.success("Avaliação salva com sucesso!")
            st.rerun()

# Função para resetar a visualização
def go_home():
    st.session_state.show_random_recipes = False
    if 'selected_recipe' in st.session_state:
        del st.session_state.selected_recipe
    st.rerun()


# Inicialização do aplicativo

st.set_page_config(
    page_title="ChefAI - Encontre Receitas",
    page_icon="🍳",
    layout="centered",
    initial_sidebar_state="expanded"
)

if 'saved_main_recipes' not in st.session_state:
    st.session_state.saved_main_recipes = []

if 'user_ratings' not in st.session_state:
    st.session_state.user_ratings = {}

if 'show_random_recipes' not in st.session_state:
    st.session_state.show_random_recipes = False

if 'all_recipes_data' not in st.session_state:
    st.session_state.all_recipes_data = {}


# Interface

col1, col2 = st.columns([5, 1])
with col1:
    st.title("🍳 Experiência Chef")
with col2:
    if st.button("🏠 Home", use_container_width=True):
        go_home()

st.markdown("Encontre receitas perfeitas com seus ingredientes ou explore novas culturas!")


# Barra Lateral 

with st.sidebar:
    if st.button("🏠 Voltar ao Início", use_container_width=True):
        go_home()

    st.header("🌍 Descubra por País")
    area_list = get_areas()
    selected_country = st.selectbox("Escolha um país:", area_list, key="country_select")

    if st.button("Mostrar Receitas Típicas"):
        st.session_state.show_random_recipes = True
        # Obtém nome original do país para a API
        try:
            if selected_country != "Todos":
                country_en = GoogleTranslator(source='pt', target='en').translate(selected_country)
            else:
                country_en = "All"
                
            st.session_state.country_recipes = get_recipes_by_area(country_en)
        except:
            st.session_state.country_recipes = []
            
        st.session_state.selected_country = selected_country
        if 'selected_recipe' in st.session_state:
            del st.session_state.selected_recipe
        st.rerun()

    st.markdown("---")
    
    st.header("📚 Receitas Pesquisadas")
    st.caption("Suas últimas receitas pesquisadas")

    if not st.session_state.saved_main_recipes:
        st.info("Nenhuma receita salva ainda. Faça uma busca!")
    else:
        for i, recipe in enumerate(st.session_state.saved_main_recipes):
            with st.expander(f"**{recipe['data']['strMeal']}**", expanded=False):
                st.caption(f"Compatibilidade: {recipe['matches']}/{recipe['total']}")
                recipe_id = recipe['data']['idMeal']
                if recipe_id in st.session_state.user_ratings:
                    rating = st.session_state.user_ratings[recipe_id]
                    st.caption(f"⭐ Sua avaliação: {rating}/5")

                if st.button("Ver Receita", key=f"view_saved_{i}"):
                    st.session_state.selected_recipe = recipe
                    st.rerun()

                if st.button("Remover", key=f"remove_saved_{i}"):
                    st.session_state.saved_main_recipes.pop(i)
                    st.rerun()

    st.markdown("---")

    st.header("⭐ Minhas Avaliações")
    if not st.session_state.user_ratings:
        st.info("Você ainda não avaliou nenhuma receita.")
    else:
        sorted_ratings = sorted(st.session_state.user_ratings.items(), key=lambda item: item[1], reverse=True)

        for recipe_id, rating in sorted_ratings:
            recipe_data_obj = st.session_state.all_recipes_data.get(recipe_id)
            if recipe_data_obj:
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                         st.markdown(f"{'⭐' * rating} - **{recipe_data_obj['data']['strMeal']}**")
                    with col2:
                        if st.button("Ver", key=f"view_rated_{recipe_id}", use_container_width=True):
                            st.session_state.selected_recipe = recipe_data_obj
                            st.rerun()
