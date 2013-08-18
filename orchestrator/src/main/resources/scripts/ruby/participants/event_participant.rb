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
      workflow_name = workitem.sub_wf_name
      workflow_id = workitem.wfid

      event['workflow_id'] = workflow_id
      event['workflow_name'] = workflow_name

      if workitem.fields.has_key? NODE
        node = workitem.fields[NODE]
        parts = node['id'].split('.')
        event['node'] = parts[1]
        event['app'] = parts[0]
      end

      $user_logger.debug("[workflow] - #{event}")

      reply(workitem)

    rescue Exception => e
      flunk(workitem, e)
    end
  end

end