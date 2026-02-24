from langgraph.graph import StateGraph, START, END, MessagesState
from typing import Dict, List
from langchain.agents import create_agent
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.types import Send
from ..schema.booking_details import TravelSearchResultCollection, TravelSearchResult
from ..schema.scraping_result import ScrapingResultCollection
from ..schema.name_extraction import NameExtractionResult, NameExtractionResultCollection
from shared.prompt_registry.destination_recommendation import DESTINATION_PROFILE_INSTRUCTION, WEB_SEARCH_INSTRUCTION, SCRAPE_PAGE_INSTRUCTION, NAME_EXTRACTION_INSTRUCTION
from shared.prompt_registry.general import JSON_RETURN_INSTRUCTION, TRANSPERANCY_INSTRUCTION
from ..utils.middleware import handle_tool_errors
from ..schema.graph_states import RecommendationState
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import LanguageModelLike, BaseLanguageModel
from shared.utils.helpers import describe_model, merge_ner_locations, filter_similar_phrases
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
import demjson3 as demjson


class RecommendationSubgraph(StateGraph):
    def __init__(self, llm: BaseLanguageModel, toolkit):
        self.llm = llm
        self.toolkit = toolkit
        super().__init__(RecommendationState)
    
    async def _perform_web_search(self, state: RecommendationState):
        last_message = state['messages'][-1]
        requirements_gathered = state['requirements_gathered']
        system_prompt = PromptTemplate.from_template(WEB_SEARCH_INSTRUCTION + JSON_RETURN_INSTRUCTION + TRANSPERANCY_INSTRUCTION)
        fields = [
            f"""
            {field}:  {field_info.description}. Consider {'null' if field_info.default is None else field_info.default} if not provided,
            """
            for field, field_info in TravelSearchResult.model_fields.items()
        ]
        struct = f"""
            {{
                "search_results": [
                    {{
                        {"\n".join(fields)}
                    }}
                ]
            }}
        """
        system_prompt = system_prompt.format(source_count = 5, user_preferences = requirements_gathered, structure=struct)
        
        # CAnt use response format since multiple tool calls throw error
        # even if same tool is called twice in parallel. Model needs to be given explicit instruction to 
        # concatenate multiple tool call results but prompting is unreliable
        agent = create_agent(model=self.llm, tools=self.toolkit, system_prompt=system_prompt,  middleware=[handle_tool_errors]) 
        response = await agent.ainvoke({'messages':[last_message]})

        try:
            ai_response = response['messages'][-1]
            response = JsonOutputParser().parse(ai_response.content)
        except OutputParserException as e:
            response = demjson.decode(ai_response.content)
        except Exception:
            print(e)
        results: TravelSearchResultCollection = TravelSearchResultCollection.model_validate(response)
        return {'web_search_results': results.search_results[:5]}
    
    async def _parse_webpage(self, state: RecommendationState):
        last_message = state['messages'][-1]
        web_search_results: list[TravelSearchResult] = state['web_search_results']
        struct = describe_model(ScrapingResultCollection)
        system_prompt = PromptTemplate.from_template(SCRAPE_PAGE_INSTRUCTION + JSON_RETURN_INSTRUCTION).format(scraping_sources=[result.url for result in web_search_results], structure=struct)

        agent = create_agent(model=self.llm, tools=self.toolkit, system_prompt=system_prompt,  middleware=[handle_tool_errors]).with_retry(retry_if_exception_type=(OutputParserException, ))
        response = await agent.ainvoke({'messages': [last_message]})

        try:
            ai_response = response['messages'][-1]
            response = JsonOutputParser().parse(ai_response.content)
        except OutputParserException as e:
            response = demjson.decode(ai_response.content)
        except Exception:
            print(e)
        results: ScrapingResultCollection = ScrapingResultCollection.model_validate(response)
        return {'scraping_results': results.scraping_results[:3]}

    def _broadcast_scraping_results(self, state: RecommendationState):
        _ = []
        for result in state['scraping_results']:
            _.append(Send('extract_places', {**state, 'scraping_result': result.model_dump()}))
        return _
    
    async def _investigate_place(self, state: RecommendationState):
        last_message = state['messages'][-1]
        travel_info = {'destination': state['recommendation'], **state['requirements_gathered']}
        system_prompt = PromptTemplate.from_template(DESTINATION_PROFILE_INSTRUCTION).format(travel_info=travel_info)
        agent = create_agent(model=self.llm, tools=self.toolkit, system_prompt=system_prompt, middleware=[handle_tool_errors])

        response = await agent.ainvoke({'messages': last_message})
        try:
            ai_response = response['messages'][-1]
        except Exception as e:
            print(e)

        return {'investigation_report': f"{ai_response.content}\n\n"}
    
    async def _extract_places(self, state: RecommendationState):
        try:
            d = []
            scraping_result =  state['scraping_result']  # scraping_result is a deliberate key name not in the REcommendationState but used to send Send() in broadcase_scraping_result
            tokenizer = AutoTokenizer.from_pretrained("dslim/bert-large-NER")
            model = AutoModelForTokenClassification.from_pretrained("dslim/bert-large-NER")

            nlp = pipeline("ner", model=model, tokenizer=tokenizer)
            result = nlp(scraping_result['content'])
            # Merge B-LOC and I-LOC
            places_found_with_ner  = merge_ner_locations(result)
            places_found_with_ner = [r['word']+"\n" for r in places_found_with_ner]

            with open('ner result.txt', 'a+') as file:
                file.writelines(places_found_with_ner)
                file.write('=============================\n')
        except ValueError as e:
            print("Value error", e)
        return {'extracted_names': places_found_with_ner}
        
    def filter_duplicates(self, state: RecommendationState):

        # 'extracted_names' key in graph state is annotated with oeprator.add
        # Hence, each time this function is invoked, the resulting list is appended to an existing list of 'extracted_names'
        # even if the call to this function was placed with Send() API which is for parallel execution
        extracted_names = set([n.lower().strip() for n in state['extracted_names']])
        # Approximate matching to filter duplicates
        final_list = filter_similar_phrases(extracted_names)
        return {'extracted_names': final_list}

    def _broadcast_extraction_result(self, state: RecommendationState):
        _ = []
        for destination in state['extracted_names']:
            _.append(Send('investigate_place', {**state, 'recommendation': destination}))
        return _

    def _create_recommendation_subgraph(self):
        destination_recommendation_subgraph = StateGraph(RecommendationState)
        self._create_recommendation_nodes(destination_recommendation_subgraph)
        self._connect_recommendation_nodes(destination_recommendation_subgraph)

        return destination_recommendation_subgraph.compile()

    def _create_recommendation_nodes(self, graph: StateGraph):
        graph.add_node("perform_websearch", self._perform_web_search)
        graph.add_node("parse_webpage", self._parse_webpage)
        graph.add_node("extract_places", self._extract_places)
        graph.add_node("filter_duplicate_names", self.filter_duplicates)
        graph.add_node("investigate_place", self._investigate_place)

    def _connect_recommendation_nodes(self, graph: StateGraph):
        graph.add_edge(START, "perform_websearch")
        graph.add_edge("perform_websearch", "parse_webpage")
        graph.add_conditional_edges("parse_webpage", self._broadcast_scraping_results, ['extract_places'])
        graph.add_edge("extract_places", "filter_duplicate_names")
        graph.add_conditional_edges("filter_duplicate_names", self._broadcast_extraction_result, ['investigate_place'])
        graph.add_edge("investigate_place", END)
