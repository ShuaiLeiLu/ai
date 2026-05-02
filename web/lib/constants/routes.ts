export const routes = {
  home: '/',
  login: '/login',
  workstation: '/workstation',
  // 核心模块
  aiResearcher: '/workstation/ai-researcher',
  researcherMarket: '/workstation/researcher-market',
  researcherEditor: '/workstation/researcher-editor',
  documents: '/workstation/documents',
  community: '/workstation/community',
  newsAnalysis: '/workstation/news-analysis',
  preopen: '/workstation/overview',
  tasks: '/workstation/tasks',
  trading: '/workstation/trading',
  tradingDetail: (researcherId: string): `/workstation/trading/${string}` =>
    `/workstation/trading/${researcherId}`,
  billing: '/workstation/billing',
  userGuide: '/workstation/user-guide',
  // 极睿实验室子页面
  labKnowledgeBase: '/workstation/knowledge-base',
  labCreateResearcher: '/workstation/my-researchers',
  labTalentMarket: '/workstation/talent-market',
  labSkillMarket: '/workstation/skill-market',
  labMcpMarket: '/workstation/mcp-market',
} as const;
