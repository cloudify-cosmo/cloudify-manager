class EventParticipant < Ruote::Participant

  NODE = 'node'
  EVENT = 'event'

  def do_not_thread
    true
  end

  def on_workitem
    begin

      raise 'event not set' unless workitem.params.has_key? EVENT
      event = workitem.params[EVENT]
      sub_workflow_name = workitem.sub_wf_name
      workflow_name = workitem.wf_name

      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        parts = node['id'].split('.')
        event['node'] = parts[1]
        event['app'] = parts[0]
      end

      if sub_workflow_name == workflow_name
        # no need to print sub workflow if there is none
        $user_logger.debug("[#{workflow_name}] - #{event}")
      end



      $user_logger.debug("[#{workflow_name}.#{sub_workflow_name}] - #{event}")

      reply(workitem)

    rescue Exception => e
      flunk(workitem, e)
    end
  end

end