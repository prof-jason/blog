export type WritingPrompt = {
  subject: string;
  prompt: string;
  example: string;
};

export const PROMPTS: WritingPrompt[] = [
  {
    subject: "A Forgotten Object",
    prompt:
      "Describe an object you once loved but haven't touched in years. Where is it now, and what would it say about you if it could speak?",
    example:
      "My red harmonica lives in the junk drawer, wedged between dead batteries and a takeout menu. If it could talk, it would remind me that I once practiced every night on the back steps, convinced I'd be famous by summer. It would say I quit too early, and it would be right.",
  },
  {
    subject: "The Kitchen Table",
    prompt:
      "Write about a single meal at a kitchen table. Use at least three senses, and let one small moment reveal how the people there feel about each other.",
    example:
      "The soup was too salty, but nobody said so. Dad tore his bread in half and slid the bigger piece toward my sister without looking up. The radiator ticked. That was how we apologized in our house: with bread, never with words.",
  },
  {
    subject: "Weather",
    prompt:
      "Choose one kind of weather and write a scene where it changes a character's plans. Let the weather mirror what the character is feeling.",
    example:
      "The fog came in before the bus did. Marisol watched the stop sign dissolve into grey and felt, for the first time all week, that she didn't have to see what was coming next. She pulled up her hood and decided to walk.",
  },
  {
    subject: "A First Time",
    prompt:
      "Recall the first time you did something that scared you. Slow the moment down: what happened in the ten seconds right before you did it?",
    example:
      "The diving board was rough under my toes. I counted the ceiling tiles—fourteen—then counted them again. Behind me, someone coughed. My heart was louder than the pool fans. I thought, if I don't go now, I'll climb down, and I'll be someone who climbs down. So I went.",
  },
  {
    subject: "A Stranger",
    prompt:
      "Invent a life story for a stranger you noticed recently. Give them one secret and one habit that hints at it.",
    example:
      "The man at the laundromat folds every shirt twice, corners exactly matched. He was a sailor once, and he still packs as if the ship might leave without him. He never mentions the sea, but he checks the clock like it's the tide.",
  },
  {
    subject: "Home",
    prompt:
      "Write about home without describing a building. What sounds, people, or routines make a place feel like home to you?",
    example:
      "Home is the squeak of the third stair and my grandmother humming off-key while she irons. It's knowing which cabinet sticks. It's a porch light left on, even when everyone is already inside.",
  },
  {
    subject: "A Letter to Your Future Self",
    prompt:
      "Write a letter to yourself ten years from now. Ask three questions you genuinely want answered.",
    example:
      "Dear Future Me, Did you ever learn to cook something besides pasta? Are you still friends with Jordan? And most importantly—did you stop being afraid to raise your hand? I hope so. I'm trying, from back here.",
  },
  {
    subject: "An Argument",
    prompt:
      "Write a short dialogue between two people who disagree about something small, but are really arguing about something bigger.",
    example:
      "\"You left the lights on again.\" \"It's one lamp.\" \"It's always one lamp.\" \"Is this really about the lamp?\" She didn't answer. She just switched it off and stood there in the dark, waiting for him to say he'd call his mother.",
  },
  {
    subject: "The View From a Window",
    prompt:
      "Describe what you can see from a window you know well. Then describe what you wish you could see instead.",
    example:
      "From my bedroom window I can see the parking lot, a leaning basketball hoop, and a maple that turns orange before any other tree on the street. I wish I could see the ocean. Instead I watch the maple, and every October it's close enough.",
  },
  {
    subject: "A Lost Skill",
    prompt:
      "Write about something people used to know how to do that is disappearing. Argue for why it's worth keeping.",
    example:
      "My great-aunt could darn a sock so neatly you couldn't find the hole. Nobody darns socks now; we just buy more. But mending teaches patience—the idea that something broken is worth an evening of your attention. We could use more of that.",
  },
  {
    subject: "Music",
    prompt:
      "Pick a song that is tied to a specific memory. Write the memory without naming the song, and let the reader hear it anyway.",
    example:
      "The car windows were down and the chorus came around for the third time, and all four of us shouted it, badly, at a red light. The woman in the next car laughed and turned hers up too. For three minutes, the whole intersection was in the same band.",
  },
  {
    subject: "A Door",
    prompt:
      "Write a scene that begins with a character standing in front of a closed door. Don't reveal what's behind it until the last sentence.",
    example:
      "Theo raised his hand to knock and lowered it. He smoothed his shirt. He rehearsed his opening line twice, then a third time with a smile. He could hear laughter on the other side, and dishes, and a dog. Finally he knocked—and his daughter opened the door.",
  },
];
