from chats.formatting import format_to_xml, render_message_inner_xml
from chats.model import ConversationFlags, Message

flags = ConversationFlags()
msg = Message(role="user", index=1, text="<thinking is my hobby\nand a second line")
print("=== PYTHON format_to_xml ===")
print(format_to_xml([msg], flags))
print("=== PYTHON render_message_inner_xml ===")
print(render_message_inner_xml(msg, flags))
