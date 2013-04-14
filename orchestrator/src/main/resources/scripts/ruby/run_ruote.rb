require 'rubygems'
require 'ruote'
require 'java'

class JavaClassParticipant < Ruote::Participant
  def on_workitem
    puts '--- JavaClassParticipant invocation:'

    puts 'workitem.fields:'
    puts workitem.fields['appliance']

    java_class_name = workitem.params['class']
    java_participant = eval("#{java_class_name}.new")
    java_participant.execute()

    puts '--- DONE.'
    puts "\n"

    reply
  end
end

engine = Ruote::Engine.new(Ruote::Worker.new(Ruote::HashStorage.new))
engine.register_participant 'java', JavaClassParticipant

radial_workflow = Ruote::RadialReader.read($workflow)

wfid = engine.launch(radial_workflow, 'appliances' => $appliances)
engine.wait_for(wfid)
