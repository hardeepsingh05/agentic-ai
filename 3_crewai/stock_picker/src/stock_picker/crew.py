from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from pydantic import BaseModel, Field
from stock_picker.tools.custom_tool import CustomTavilySearchTool
from stock_picker.tools.custom_tool import send_email_tool

# setting up the pydantic BaseModel class's subclass
class TrendingCompany(BaseModel):
    """A company that is in the news and attracting attention """
    name: str = Field(
        description="Company name"
    )
    ticker: str = Field(
        description="Stock ticker symbol"
    )
    reason: str = Field(
        description="Reason why this company is trending in the news"
    )

class TrendingCompanyList(BaseModel):
    """List of multiple trending companies that are in the news"""
    companies: list[TrendingCompany] = Field(
        description="List of companies trending in the news"
    )

class TrendingCompanyResearch(BaseModel):
    """ Detailed research on a company """
    name: str = Field(
        description="Company name"
    )
    market_position: str = Field(
        description="Current market postion and competitive analysis"
    )
    future_outlook: str = Field(
        description="Future outlook and growth prospects"
    )
    investment_potential: str = Field(
        description="Investment potential and suitability for investment"
    )

class TrendingCompaniesResearchList(BaseModel):
    """ A list of detailed research on all the companies """
    research_list: list[TrendingCompanyResearch] = Field(
        description="Comprehensive research on all trending companies"
    )

@CrewBase
class StockPicker():
    """StockPicker crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def trending_company_finder(self) -> Agent:
        return Agent(
            config=self.agents_config['trending_company_finder'], # type: ignore[index]
            verbose=True,
            tools=[CustomTavilySearchTool()],
            memory=True
        )

    @agent
    def financial_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['financial_researcher'], # type: ignore[index]
            verbose=True,
            tools=[CustomTavilySearchTool()],
            memory=True
        )

    @agent
    def stock_picker(self) -> Agent:
        return Agent(
            config=self.agents_config['stock_picker'],
            verbose=True,
            tools = [send_email_tool],
            memory=True
        )

    @task
    def find_trending_companies(self) -> Task:
        return Task(
            config=self.tasks_config['find_trending_companies'], # type: ignore[index]
            output_pydantic=TrendingCompanyList
        )

    @task
    def research_trending_companies(self) -> Task:
        return Task(
            config=self.tasks_config['research_trending_companies'], # type: ignore[index]
            output_pydantic=TrendingCompaniesResearchList
        )

    @task
    def pick_best_company(self) -> Task:
        return Task(
            config=self.tasks_config['pick_best_company']
        )
    
    @crew
    def crew(self) -> Crew:
        """Creates the StockPicker crew"""

        manager = Agent(
            config=self.agents_config['manager'],
            allow_delegation=True
        )

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.hierarchical,
            verbose=True,
            tracing=True,
            memory=True,
            manager_agent=manager
        )
