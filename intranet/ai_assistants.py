from django_ai_assistant import AIAssistant

class TourplanFileAIAssistant(AIAssistant):
    id = "tourplan_file_assistant"
    name = "Tourplan File Assistant"
    instructions = "Read the uploaded file and shows the user the possible new trips that are not already existing."
    model = "gpt-4o"