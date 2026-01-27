from langgraph.graph import StateGraph, START, END, MessagesState
from typing import Dict, List
from langchain.agents import create_agent
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from ..schema.booking_details import TravelSearchResultCollection, TravelSearchResult
from ..schema.scraping_result import ScrapingResultCollection
from shared.prompt_registry.destination_recommendation import WEB_SEARCH_INSTRUCTION, SCRAPE_PAGE_INSTRUCTION
from shared.prompt_registry.general import JSON_RETURN_INSTRUCTION, TRANSPERANCY_INSTRUCTION
from ..utils.middleware import handle_tool_errors
from ..schema.graph_states import RecommendationState


class RecommendationSubgraph(StateGraph):
    def __init__(self, llm, toolkit):
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
        for t in self.toolkit:
            print(t.name)
        # CAnt use response format since multiple tool calls throw error
        # even if same tool is called twice in parallel. Model needs to be given explicit instruction to 
        # concatenate multiple tool call results but prompting is unreliable
        agent = create_agent(model=self.llm, tools=self.toolkit, system_prompt=system_prompt,  middleware=[handle_tool_errors]) 
        response = await agent.ainvoke({'messages':[last_message]})

        try:
            ai_response = response['messages'][-1]
            response = JsonOutputParser().parse(ai_response.content)
        except Exception as e:
            print(e)
        results: TravelSearchResultCollection = TravelSearchResultCollection.model_validate(response)
        return {'web_search_results': results.search_results}
    
    def _parse_webpage(self, state: RecommendationState):
        web_search_results: list[TravelSearchResult] = state['web_search_results']
        prompt = PromptTemplate.from_template(SCRAPE_PAGE_INSTRUCTION + JSON_RETURN_INSTRUCTION)
        chain = prompt | self.llm | JsonOutputParser()

        struct = ""
        for field, field_info in ScrapingResultCollection.model_fields.items():
            if field_info.default_factory is not None:
                dfault = f"Consider {eval(field_info.default_factory.__name__)()} if not provided"
            else:
                dfault = f"Consider {'null' if field_info.default is None else field_info.default} if not provided"
            struct += f"{field}: {field_info.description}. {dfault}\n"
        
        response = chain.invoke({
            'scraping_sources': [result.url for result in web_search_results],
            'structure': struct
        })
        return {'scraping_result': response}
    
    
    def _md_conversion(self, state: RecommendationState):
        ...

    def _investigate_places(self, state: RecommendationState):
        ...
    
    def _create_recommendation_subgraph(self):
        destination_recommendation_subgraph = StateGraph(RecommendationState)
        self._create_recommendation_nodes(destination_recommendation_subgraph)
        self._connect_recommendation_nodes(destination_recommendation_subgraph)

        return destination_recommendation_subgraph.compile()

    def _create_recommendation_nodes(self, graph: StateGraph):
        graph.add_node("perform_websearch", self._perform_web_search)
        graph.add_node("parse_webpage", self._parse_webpage)
        graph.add_node("convert_to_markdown", self._md_conversion)
        graph.add_node("investigate_places", self._investigate_places)

    def _connect_recommendation_nodes(self, graph: StateGraph):
        graph.add_edge(START, "perform_websearch")
        graph.add_edge("perform_websearch", "parse_webpage")
        graph.add_edge("parse_webpage", "convert_to_markdown")
        graph.add_edge("convert_to_markdown", "investigate_places")
        graph.add_edge("investigate_places", END)
